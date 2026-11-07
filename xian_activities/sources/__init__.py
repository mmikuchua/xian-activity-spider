# -*- coding: utf-8 -*-
"""数据源注册表：新增站点只需要在这里加一行。"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Tuple

from ..models import Activity

logger = logging.getLogger(__name__)

SOURCES = {
    "bendibao": "西安本地宝",
    "snpac": "陕西大剧院",
    "sxlib": "陕西省图书馆",
}


def crawl_all(source: str = "all", limit: int | None = None) -> Tuple[List[Activity], Dict]:
    """抓取指定数据源。

    单个来源失败不会中断其它来源；返回 (活动列表, 报告)。
    """
    if source != "all" and source not in SOURCES:
        raise ValueError(f"未知数据源 {source}，可选：all / {', '.join(SOURCES)}")

    names = list(SOURCES) if source == "all" else [source]
    activities: List[Activity] = []
    report: Dict = {"ok": [], "failed": [], "count": 0, "duration_s": 0.0}
    started = time.time()

    for name in names:
        module = __import__(f"{__name__}.{name}", fromlist=["fetch"])
        source_started = time.time()
        try:
            items = module.fetch(limit=limit)
            activities.extend(items)
            report["ok"].append(
                {"source": name, "count": len(items), "duration_s": round(time.time() - source_started, 1)}
            )
            logger.info("%s: %s 条", SOURCES[name], len(items))
        except Exception as exc:  # noqa: BLE001 - 单个来源失败不影响整批
            logger.warning("%s 抓取失败：%s", SOURCES[name], exc)
            report["failed"].append({"source": name, "error": str(exc)})

    report["count"] = len(activities)
    report["duration_s"] = round(time.time() - started, 1)
    return activities, report


__all__ = ["crawl_all", "SOURCES", "bendibao", "snpac", "sxlib"]
