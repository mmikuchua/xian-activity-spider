# -*- coding: utf-8 -*-
"""陕西省图书馆 · 陕图讲坛（讲座预告）。

列表页是静态 HTML（ul#zebra），直接 HTTP 抓取即可，不再需要浏览器。
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from bs4 import BeautifulSoup

from ..dates import parse_date_range
from ..http import get
from ..models import Activity

logger = logging.getLogger(__name__)

SOURCE = "陕西省图书馆"
LIST_URL = "https://www.sxlib.org.cn/hd/hdyg/stjt/"

TITLE_DATE = re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日[^：:]{0,10}?([上下]午)?")


def _date_from_title(name: str) -> tuple[Optional[str], Optional[str]]:
    match = TITLE_DATE.search(name)
    if not match:
        return None, None
    year, month, day, period = match.groups()
    start, end = parse_date_range(f"{year}年{month}月{day}日")
    if start and period:
        hour = "14:00" if period == "下" else "09:00"
        start = f"{start[:10]}T{hour}"
    return start, start


def parse_list(html: str) -> List[Activity]:
    soup = BeautifulSoup(html, "html.parser")
    listing = soup.find("ul", id="zebra")
    if listing is None:
        return []
    activities: List[Activity] = []
    for index, item in enumerate(listing.find_all("li", recursive=False), 1):
        anchor = item.find("a")
        title_node = item.find("font")
        date_node = item.find("span")
        name = title_node.get_text(strip=True) if title_node else ""
        if not name and anchor:
            name = anchor.get_text(strip=True)
        if not name:
            continue
        link = ""
        if anchor and anchor.get("href"):
            link = anchor["href"]
            if not link.startswith("http"):
                link = "https://www.sxlib.org.cn" + link
        valid_start, valid_end = _date_from_title(name)
        activities.append(
            Activity(
                name=name,
                source=SOURCE,
                source_id=f"sxlib-{index}",
                category_text="讲座沙龙",
                time_text=date_node.get_text(strip=True) if date_node else "",
                address="陕西省图书馆",
                price_text="免费（公益讲座）",
                highlights="陕图讲坛公益讲座，具体主题与报名方式见详情页。",
                link=link,
                valid_start=valid_start,
                valid_end=valid_end,
                tags={
                    "categories": ["B"],
                    "demand": ["B"],
                    "comfort": ["A"],
                    "factors": ["A", "C"],
                    "age_fit": ["B", "C", "D"],
                    "time_slots": ["B"],
                    "themes": ["陕图讲坛", "讲座", "人文"],
                    "moods": ["安静"],
                    "audience": ["文化爱好者"],
                },
            )
        )
    return activities


def fetch(limit: Optional[int] = None) -> List[Activity]:
    html = get(LIST_URL, timeout=25)
    activities = parse_list(html)
    if not activities:
        raise RuntimeError("sxlib: 未解析到讲座，页面结构可能已变化")
    logger.info("sxlib: 解析到 %s 条讲座", len(activities))
    return activities[:limit] if limit else activities
