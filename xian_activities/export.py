# -*- coding: utf-8 -*-
"""把原始/增强后的活动数据导出为站点可直接消费的 activities.json。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .models import SCHEMA_VERSION, Activity


def build_payload(activities: Iterable[Activity], *, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    items = sorted(activities, key=lambda item: (item.name, item.id))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "count": len(items),
        "meta": meta or {},
        "activities": [item.to_dict() for item in items],
    }


def write_json(activities: List[Activity], out_path: Path, *, meta: Dict[str, Any] | None = None) -> Path:
    payload = build_payload(activities, meta=meta)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    # 顺手写一份 JS 包装，方便 file:// 预览时直接 <script> 引入（可选）
    return out_path
