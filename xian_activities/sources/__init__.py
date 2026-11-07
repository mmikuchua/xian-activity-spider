# -*- coding: utf-8 -*-
"""数据源注册表。

新增站点只需要写一个 `fetch(limit)` 并在 SOURCES 里登记。
标了 `http` 的数据源只依赖 HTTP + BeautifulSoup，可以在 GitHub Actions 里跑；
标了 `browser` 的依赖本机 Chrome（人机验证场景下的兜底）。
"""

from __future__ import annotations

import importlib
import logging
import time
from typing import Dict, List, Tuple

from ..models import Activity, dedupe

logger = logging.getLogger(__name__)

# name: (展示名, 类型)
SOURCES: Dict[str, Tuple[str, str]] = {
    "douban": ("豆瓣同城", "http"),
    "huodongxing": ("活动行", "http"),
    "bendibao_http": ("西安本地宝", "http"),
    "sxhm": ("陕西历史博物馆", "http"),
    "sxlib": ("陕西省图书馆", "http"),
    "snpac": ("陕西大剧院", "browser"),
    "bendibao": ("西安本地宝", "browser"),
}

HTTP_SOURCES = [name for name, (_, kind) in SOURCES.items() if kind == "http"]
BROWSER_SOURCES = [name for name, (_, kind) in SOURCES.items() if kind == "browser"]


def resolve(source: str, *, http_only: bool = False) -> List[str]:
    if source in ("all", ""):
        return HTTP_SOURCES if http_only else list(SOURCES)
    if source not in SOURCES:
        raise ValueError(f"未知数据源 {source}，可选：all / {', '.join(SOURCES)}")
    return [source]


def crawl_all(source: str = "all", limit: int | None = None, http_only: bool = False) -> Tuple[List[Activity], Dict]:
    """抓取指定数据源。单个来源失败不会中断其它来源。"""
    names = resolve(source, http_only=http_only)
    activities: List[Activity] = []
    report: Dict = {"ok": [], "failed": [], "count": 0, "duration_s": 0.0, "skipped": []}
    started = time.time()

    for name in names:
        display, kind = SOURCES[name]
        if http_only and kind == "browser":
            report["skipped"].append({"source": name, "reason": "需要浏览器，已在 http-only 模式下跳过"})
            continue
        module = importlib.import_module(f"{__name__}.{name}")
        source_started = time.time()
        try:
            items = module.fetch(limit=limit)
            activities.extend(items)
            report["ok"].append(
                {"source": name, "display": display, "count": len(items), "duration_s": round(time.time() - source_started, 1)}
            )
            logger.info("%s: %s 条", display, len(items))
        except Exception as exc:  # noqa: BLE001 - 单个来源失败不影响整批
            logger.warning("%s 抓取失败：%s", display, exc)
            report["failed"].append({"source": name, "display": display, "error": str(exc)[:200]})

    report["count"] = len(activities)
    report["duration_s"] = round(time.time() - started, 1)
    return dedupe(activities), report


def source_names() -> Dict[str, str]:
    return {name: display for name, (display, _) in SOURCES.items()}


__all__ = ["crawl_all", "SOURCES", "HTTP_SOURCES", "BROWSER_SOURCES", "source_names", "resolve"]
