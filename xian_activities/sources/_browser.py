# -*- coding: utf-8 -*-
"""共享的无头浏览器工具。

三个数据源都是 JS 渲染页面，所以用 Selenium；但把「启动浏览器」收敛到这里，
数据源模块只关心「怎么解析」，测试时可以完全离线跑。
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def headless_enabled() -> bool:
    return os.getenv("HEADLESS", "1").lower() not in ("0", "false", "no")


@contextmanager
def browser() -> Iterator["object"]:
    """打开一个 Chrome 实例，退出时自动关闭。"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
    except ImportError as exc:  # pragma: no cover - 环境问题
        raise RuntimeError("缺少 selenium，请先安装：pip install selenium") from exc

    options = webdriver.ChromeOptions()
    if headless_enabled():
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(f"--user-agent={os.getenv('SPIDER_USER_AGENT', DEFAULT_UA)}")

    binary = os.getenv("CHROME_BINARY")
    if binary:
        options.binary_location = binary

    driver_path = os.getenv("CHROMEDRIVER")
    driver = webdriver.Chrome(
        service=Service(executable_path=driver_path) if driver_path else Service(),
        options=options,
    )
    driver.set_page_load_timeout(int(os.getenv("PAGE_LOAD_TIMEOUT", "45")))
    try:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    except Exception:  # noqa: BLE001 - 部分页面上下文不允许
        pass
    try:
        yield driver
    finally:
        try:
            driver.quit()
        except Exception:  # noqa: BLE001
            logger.warning("关闭浏览器失败", exc_info=True)


def load_html(url: str, *, wait_css: Optional[str] = None, timeout: int = 25) -> str:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    with browser() as driver:
        driver.get(url)
        if wait_css:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_css))
            )
        return driver.page_source
