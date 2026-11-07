# -*- coding: utf-8 -*-
"""豆瓣同城 · 西安活动。

豆瓣的「最近一周同城活动」是静态 HTML，分页 ?start=0,10,20…，
每页 10 条，字段（时间/地点/费用/海报）齐全，非常适合做活动源。
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from bs4 import BeautifulSoup

from ..http import get
from ..models import Activity, clean_title

logger = logging.getLogger(__name__)

SOURCE = "豆瓣同城"
BASE_URL = "https://www.douban.com/location/xian/events"
# 匿名访问时分页参数无效（每页都是同一批），所以改为抓多个榜单再合并
LIST_URLS = [
    BASE_URL,
    f"{BASE_URL}/selling",
    f"{BASE_URL}/weekend",
]


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def _image(node) -> str:
    if not node:
        return ""
    return node.get("data-lazy") or node.get("src") or ""


def parse_events(html: str) -> List[Activity]:
    soup = BeautifulSoup(html, "html.parser")
    listing = soup.select_one("ul.events-list")
    if listing is None:
        return []

    activities: List[Activity] = []
    for item in listing.find_all("li", recursive=False):
        title_node = item.select_one(".title a")
        if not title_node:
            continue
        name = clean_title(title_node.get("title") or title_node.get_text())
        if not name:
            continue
        link = title_node.get("href") or ""
        start_node = item.select_one("time[itemprop='startDate']")
        end_node = item.select_one("time[itemprop='endDate']")
        start = start_node.get("datetime") if start_node else None
        end = end_node.get("datetime") if end_node else None
        venue_node = item.select_one("meta[itemprop='location']")
        address = _clean(venue_node.get("content", "")) if venue_node else ""
        if address.startswith("西安 "):
            address = address[3:]
        fee_node = item.select_one("li.fee strong")
        price_text = _clean(fee_node.get_text()) if fee_node else ""
        time_node = item.select_one(".event-time")
        time_text = _clean(time_node.get_text()) if time_node else ""
        time_text = time_text.replace("时间：", "").replace("时间:", "").strip()
        image = _image(item.select_one(".pic img"))

        activities.append(
            Activity(
                name=name,
                source=SOURCE,
                source_id=link.rstrip("/").rsplit("/", 1)[-1],
                category_text="同城活动",
                time_text=time_text,
                address=address or "西安",
                price_text=price_text,
                highlights="",
                link=link,
                cover=image,
                valid_start=start,
                valid_end=end,
                tags={"categories": [], "themes": []},
            )
        )
    return activities


def fetch(limit: Optional[int] = None) -> List[Activity]:
    from datetime import datetime, timedelta

    activities: List[Activity] = []
    seen: set[str] = set()
    cutoff = datetime.now() - timedelta(days=1)
    for index, url in enumerate(LIST_URLS):
        try:
            html = get(url, retries=2, timeout=25)
        except Exception as exc:  # noqa: BLE001 - 单个榜单失败不影响其它
            logger.warning("douban: 榜单抓取失败 %s（%s）", url, exc)
            continue
        page_items = parse_events(html)
        if not page_items and index == 0:
            raise RuntimeError("douban: 未解析到活动，可能触发了反爬或页面结构变化")
        for item in page_items:
            if item.link in seen:
                continue
            if item.valid_end:
                try:
                    if datetime.fromisoformat(item.valid_end) < cutoff:
                        continue
                except ValueError:
                    pass
            seen.add(item.link)
            activities.append(item)
        logger.info("douban: 榜单 %s 条（累计 %s）", len(page_items), len(activities))
        time.sleep(1.2)
    return activities[:limit] if limit else activities
