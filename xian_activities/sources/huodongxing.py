# -*- coding: utf-8 -*-
"""活动行 · 西安活动。

列表页是服务端渲染的卡片（标题、日期、城市、主办方），无需登录；
详情页依赖 JS，因此这里只取列表字段，城市粒度到「西安」。
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import List, Optional

from bs4 import BeautifulSoup

from ..dates import parse_month_day_range
from ..http import get
from ..models import Activity, clean_title

logger = logging.getLogger(__name__)

SOURCE = "活动行"
BASE = "https://www.huodongxing.com"
LIST_URL = "https://www.huodongxing.com/events?city=%E8%A5%BF%E5%AE%89"
MAX_PAGES = int(os.getenv("HDX_PAGES", "2"))

# 活动行以商业培训/行业会议为主，只保留偏公共文化的活动
CULTURE_HINTS = (
    "剧", "舞", "音乐", "演唱会", "相声", "曲艺", "展览", "展映", "艺术", "非遗", "手作", "手工",
    "亲子", "遛娃", "读书", "分享会", "签售", "放映", "电影", "讲座", "讲坛", "沙龙", "徒步",
    "夜游", "市集", "文化", "博物", "话剧", "儿童", "绘本", "诗", "书法", "摄影", "汉服",
    "戏曲", "秦腔", "歌剧", "交响", "民乐", "合唱", "演出", "音乐会", "庙会", "游园",
)
BIZ_HINTS = (
    "培训", "研修", "峰会", "大会", "论坛", "研讨会", "招商", "加盟", "招聘", "创业", "营销",
    "获客", "电商", "跨境", "对接会", "选品", "申报", "课程", "总裁班", "工作坊", "meetup",
    "开发者", "变现", "出海", "增长", "运营", "品牌", "产业", "连锁", "建企", "毕业典礼", "招生",
)


def is_cultural(name: str) -> bool:
    text = (name or "").lower()
    if any(word.lower() in text for word in BIZ_HINTS):
        return False
    return any(word in text for word in CULTURE_HINTS)


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def parse_events(html: str) -> List[Activity]:
    soup = BeautifulSoup(html, "html.parser")
    activities: List[Activity] = []
    for card in soup.select(".search-tab-content-item-mesh"):
        title_node = card.select_one(".item-title")
        if not title_node:
            continue
        name = clean_title(title_node.get_text(" "))
        if not name or not is_cultural(name):
            continue
        link = title_node.get("href") or ""
        if link.startswith("/"):
            link = BASE + link
        date_node = card.select_one(".item-dress p")
        time_text = _clean(date_node.get_text()) if date_node else ""
        city_node = card.select_one(".item-dress-pp")
        city = _clean(city_node.get_text()) if city_node else "西安"
        start, end = parse_month_day_range(time_text)
        logo = card.select_one("img.item-logo")
        organizer = card.select_one(".user-name")
        activities.append(
            Activity(
                name=name,
                source=SOURCE,
                source_id=re.sub(r"\D", "", link)[-12:] or name,
                category_text="同城活动",
                time_text=time_text,
                address=city,
                price_text="",
                highlights=_clean(organizer.get_text()) if organizer else "",
                link=link,
                cover=(logo.get("src") if logo else "") or "",
                valid_start=start,
                valid_end=end or start,
                tags={"categories": [], "themes": []},
            )
        )
    return activities


def fetch(limit: Optional[int] = None) -> List[Activity]:
    activities: List[Activity] = []
    for page in range(1, MAX_PAGES + 1):
        url = LIST_URL if page == 1 else f"{LIST_URL}&page={page}"
        html = get(url, retries=2, timeout=25)
        page_items = parse_events(html)
        if not page_items:
            if page == 1:
                raise RuntimeError("huodongxing: 未解析到活动，页面结构可能已变化")
            break
        activities.extend(page_items)
        logger.info("huodongxing: 第 %s 页 %s 条", page, len(page_items))
        if len(page_items) < 20:
            break
        time.sleep(1.2)
    return activities[:limit] if limit else activities
