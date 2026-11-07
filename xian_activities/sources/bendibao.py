# -*- coding: utf-8 -*-
"""西安本地宝 · 活动日历。

站点有拼图人机验证，CI/无头环境经常会被拦；拦截时抛出明确异常，
由上层决定「沿用旧数据」而不是写入空结果。
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from bs4 import BeautifulSoup

from ..models import Activity
from ._browser import browser

logger = logging.getLogger(__name__)

SOURCE = "西安本地宝"
LIST_URL = "https://xa.bendibao.com/xiuxian/huodongrili/"
MAX_CLICKS = 30


def _detail(container, keyword: str) -> str:
    for block in container.find_all("div", class_="main-single-block-msg"):
        label = block.find("span", class_="main-single-block-des")
        if not label or keyword not in block.get_text():
            continue
        spans = block.find_all("span")
        if len(spans) > 1:
            return spans[1].get_text(strip=True)
    return ""


def parse_list(html: str) -> List[Activity]:
    """把列表页 HTML 解析成 Activity 列表（纯函数，便于离线测试）。"""
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.find_all("div", class_="main-block-single")
    activities: List[Activity] = []
    for index, container in enumerate(containers, 1):
        title_node = container.find(class_="main-single-block-titles")
        name = title_node.get_text(strip=True) if title_node else ""
        if not name:
            continue
        time_node = container.find(class_="time-dia-hover")
        link_node = container.find("a", class_="ticket-buttons")
        link = link_node.get("href", "") if link_node else ""
        if link.startswith("/"):
            link = "https://xa.bendibao.com" + link
        highlights = _detail(container, "活动亮点")
        activities.append(
            Activity(
                name=name,
                source=SOURCE,
                source_id=f"bendibao-{index}",
                category_text="",
                time_text=(time_node.get_text(strip=True) if time_node else ""),
                address=_detail(container, "活动地址"),
                price_text="",
                highlights=highlights,
                link=link,
            )
        )
    return activities


def _assert_not_captcha(html: str) -> None:
    if "拼图验证" in html or "challenge-container" in html:
        raise RuntimeError("bendibao: 触发站点人机验证，请在本机有头模式（HEADLESS=0）下运行后再同步数据")


def _expand(driver) -> int:
    from selenium.common.exceptions import NoSuchElementException
    from selenium.webdriver.common.by import By

    clicks = 0
    while clicks < MAX_CLICKS:
        try:
            button = driver.find_element(By.ID, "showmore1")
        except NoSuchElementException:
            break
        if not button.is_displayed():
            break
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        time.sleep(0.4)
        button.click()
        clicks += 1
        time.sleep(2.0)
    return clicks


def fetch(limit: Optional[int] = None) -> List[Activity]:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    with browser() as driver:
        driver.get(LIST_URL)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "main-block-single"))
        )
        _assert_not_captcha(driver.page_source)
        clicks = _expand(driver)
        time.sleep(2)
        html = driver.page_source

    _assert_not_captcha(html)
    activities = parse_list(html)
    if not activities:
        raise RuntimeError("bendibao: 未解析到任何活动，页面结构可能已变化")
    logger.info("bendibao: 展开 %s 次，解析到 %s 条", clicks, len(activities))
    return activities[:limit] if limit else activities
