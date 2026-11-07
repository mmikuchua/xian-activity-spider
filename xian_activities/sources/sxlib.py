# -*- coding: utf-8 -*-
"""陕西省图书馆 · 陕图讲坛（讲座预告）。"""

from __future__ import annotations

import logging
from typing import List, Optional

from bs4 import BeautifulSoup

from ..models import Activity
from ._browser import browser

logger = logging.getLogger(__name__)

SOURCE = "陕西省图书馆"
LIST_URL = "https://www.sxlib.org.cn/hd/hdyg/stjt/"


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
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    with browser() as driver:
        driver.get(LIST_URL)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul#zebra")))
        html = driver.page_source

    activities = parse_list(html)
    if not activities:
        raise RuntimeError("sxlib: 未解析到讲座，页面结构可能已变化")
    logger.info("sxlib: 解析到 %s 条讲座", len(activities))
    return activities[:limit] if limit else activities
