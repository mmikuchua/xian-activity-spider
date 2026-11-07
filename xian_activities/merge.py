# -*- coding: utf-8 -*-
"""增量合并：把新抓到的活动并入现有活动库。

设计原则：
1. **只增不删**：某个数据源当天被反爬挡住时，已有活动必须保留；
2. **保留已标注内容**：同一条活动内容没变，就不重新调用大模型；
3. **允许字段更新**：档期、票价、链接这类时效字段以最新抓到为准；
4. **自然淘汰**：明确结束超过 N 天的活动不再保留，避免活动库越来越臃肿。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Iterable, List

from .models import Activity

logger = logging.getLogger(__name__)

MUTABLE_FIELDS = (
    "category_text",
    "time_text",
    "address",
    "district",
    "price_text",
    "price_level",
    "price_from",
    "link",
    "cover",
    "valid_start",
    "valid_end",
)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def merge(
    existing: Iterable[Activity],
    incoming: Iterable[Activity],
    *,
    max_age_days: int = 90,
) -> tuple[List[Activity], dict]:
    """返回 (合并后的活动列表, 统计信息)。"""
    merged: dict[str, Activity] = {activity.key: activity for activity in existing}
    stats = {"existing": len(merged), "incoming": 0, "added": 0, "updated": 0, "kept_enrichment": 0}
    now = _now_iso()

    for fresh in incoming:
        stats["incoming"] += 1
        current = merged.get(fresh.key)
        if current is None:
            fresh.seen_at = now
            merged[fresh.key] = fresh
            stats["added"] += 1
            continue

        # 保留原有的语义标签与评分（内容没变就完全不用重跑模型）
        fresh.tags = {**current.tags, **{key: value for key, value in fresh.tags.items() if value}}
        for key, value in current.scores.items():
            fresh.scores.setdefault(key, value)
        if current.enriched:
            fresh.enriched = dict(current.enriched)
            stats["kept_enrichment"] += 1

        for field in MUTABLE_FIELDS:
            value = getattr(fresh, field)
            if value not in (None, "", "unknown"):
                setattr(current, field, value)
            elif getattr(current, field) in (None, ""):
                setattr(current, field, value)
        if fresh.highlights and len(fresh.highlights) > len(current.highlights):
            current.highlights = fresh.highlights
        current.seen_at = now
        stats["updated"] += 1

    cutoff = datetime.now() - timedelta(days=max_age_days)
    kept: List[Activity] = []
    expired = 0
    for activity in merged.values():
        if activity.valid_end:
            try:
                end = datetime.fromisoformat(activity.valid_end)
            except ValueError:
                end = None
            if end and end < cutoff:
                expired += 1
                continue
        kept.append(activity)

    stats["expired_removed"] = expired
    stats["total"] = len(kept)
    logger.info(
        "合并完成：新增 %s，更新 %s，保留已有 %s，淘汰过期 %s，总计 %s",
        stats["added"],
        stats["updated"],
        stats["kept_enrichment"],
        expired,
        len(kept),
    )
    return kept, stats
