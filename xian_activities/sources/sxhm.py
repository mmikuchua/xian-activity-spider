# -*- coding: utf-8 -*-
"""陕西历史博物馆 · 临时展览。

列表页 `/Temporary.html` 是静态 HTML，每张卡片自带「时间」「地点」。
（教育活动栏目多为历史归档，噪声太大，暂不采集。）
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from bs4 import BeautifulSoup

from ..dates import parse_date_range
from ..http import get
from ..models import Activity

logger = logging.getLogger(__name__)

SOURCE = "陕西历史博物馆"
BASE = "https://www.sxhm.com"
EXHIBITION_URL = f"{BASE}/Temporary.html"


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def parse_exhibitions(html: str) -> List[Activity]:
    soup = BeautifulSoup(html, "html.parser")
    activities: List[Activity] = []
    for item in soup.select("div.item"):
        title_node = item.select_one(".text a.t1")
        if not title_node:
            continue
        name = _clean(title_node.get_text())
        if not name:
            continue
        paragraphs = [_clean(node.get_text()) for node in item.select(".t2 .p")]
        time_text = next((text for text in paragraphs if text.startswith("时间")), "")
        place_text = next((text for text in paragraphs if text.startswith("地点")), "")
        time_text = time_text.lstrip("时间：: ")
        place_text = place_text.lstrip("地点：: ")
        start, end = parse_date_range(time_text)
        image = item.select_one(".pic img")
        activities.append(
            Activity(
                name=name,
                source=SOURCE,
                source_id=title_node.get("href", "").rstrip(".html").rsplit("/", 1)[-1],
                category_text="临时展览",
                time_text=time_text,
                address=place_text or "陕西历史博物馆",
                price_text="",
                highlights="",
                link=BASE + title_node.get("href", ""),
                cover=(image.get("src") if image else "") or "",
                valid_start=start,
                valid_end=end,
                tags={"categories": ["C"], "comfort": ["A"], "themes": ["博物馆", "展览"]},
            )
        )
    return activities


def fetch(limit: Optional[int] = None) -> List[Activity]:
    activities = parse_exhibitions(get(EXHIBITION_URL, timeout=25))
    cutoff = datetime.now() - timedelta(days=7)
    fresh: List[Activity] = []
    for activity in activities:
        if activity.valid_end:
            try:
                if datetime.fromisoformat(activity.valid_end) < cutoff:
                    continue
            except ValueError:
                pass
        fresh.append(activity)
    if not fresh:
        raise RuntimeError("sxhm: 当前没有在展/即将开展的临时展览")
    return fresh[:limit] if limit else fresh
