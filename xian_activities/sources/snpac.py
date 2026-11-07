# -*- coding: utf-8 -*-
"""陕西大剧院（SNPAC）· 演出列表。

原脚本逐张卡片点进详情页再返回，慢且容易点在动画上；这里改为直接解析
列表页卡片（名称/类型/地址/票价/时间/详情链接），失败率更低。
"""

from __future__ import annotations

import logging
from typing import List, Optional

from bs4 import BeautifulSoup

from ..models import Activity
from ._browser import browser

logger = logging.getLogger(__name__)

SOURCE = "陕西大剧院"
LIST_URL = "https://www.snpac.com/sxtheatre/index.html#/index"


def _text(card, selector: str) -> str:
    node = card.select_one(selector)
    return node.get_text(strip=True) if node else ""


def parse_cards(html: str) -> List[Activity]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div[class*='program']")
    activities: List[Activity] = []
    for index, card in enumerate(cards, 1):
        name = _text(card, "[class*='program-name']") or _text(card, "h3, h4, [class*='title']")
        if not name:
            continue
        link_node = card.select_one("a[href*='ticket/detail']")
        link = link_node.get("href", "") if link_node else ""
        if link.startswith("#"):
            link = "https://www.snpac.com/sxtheatre/" + link.lstrip("#")
        elif link.startswith("/"):
            link = "https://www.snpac.com" + link
        starts = _text(card, "[class*='year']")
        activities.append(
            Activity(
                name=name,
                source=SOURCE,
                source_id=f"snpac-{index}",
                category_text=_text(card, "[class*='tip-text']") or "演出演艺",
                time_text=starts,
                address=_text(card, "[class*='address']"),
                price_text=_text(card, "[class*='price-part']"),
                highlights="",
                link=link,
            )
        )
    return activities


def fetch(limit: Optional[int] = None) -> List[Activity]:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    with browser() as driver:
        driver.get(LIST_URL)
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='program']"))
        )
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.6);")
        html = driver.page_source

    activities = parse_cards(html)
    if not activities:
        raise RuntimeError("snpac: 未解析到演出卡片，页面结构可能已变化")
    logger.info("snpac: 解析到 %s 条演出", len(activities))
    return activities[:limit] if limit else activities
