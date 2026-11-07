# -*- coding: utf-8 -*-
"""数据流水线：加载 → 去重 → LLM 语义增强 → 导出。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import settings
from .enrich import ActivityEnricher
from .export import write_json
from .models import Activity, dedupe

logger = logging.getLogger(__name__)

RAW_PATH = settings.data_dir / "raw" / "activities.json"
BUILD_PATH = settings.data_dir / "activities.json"


def load_activities(path: Path | str) -> List[Activity]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items = payload.get("activities", payload if isinstance(payload, list) else [])
    activities = []
    for item in items:
        try:
            activity = Activity.from_dict(item)
        except TypeError as exc:  # 兼容额外字段
            logger.warning("跳过一条无法解析的记录: %s (%s)", item.get("name"), exc)
            continue
        if activity.name:
            activities.append(activity)
    return dedupe(activities)


def build(
    *,
    raw_path: Path | str = RAW_PATH,
    out_path: Path | str = BUILD_PATH,
    limit: Optional[int] = None,
    use_llm: bool = True,
    use_cache: bool = True,
    offline: bool = False,
) -> Tuple[List[Activity], Dict[str, Any]]:
    activities = load_activities(raw_path)
    if limit:
        activities = activities[:limit]
    stats: Dict[str, Any] = {"loaded": len(activities), "deduped": len(activities)}

    if use_llm and not offline and settings.llm_enabled:
        enricher = ActivityEnricher(use_cache=use_cache)
        activities, enrich_stats = enricher.enrich_all(activities)
        stats.update({"enrich": enrich_stats})
    else:
        stats["enrich"] = {"skipped": True, "reason": "offline" if offline else "no api key"}

    write_json(
        activities,
        Path(out_path),
        meta={
            "pipeline": "xian-activities",
            "raw": str(raw_path),
            "llm": stats.get("enrich", {}).get("usage", {}),
        },
    )
    stats["out"] = str(out_path)
    return activities, stats
