# -*- coding: utf-8 -*-
"""把历史 SQLite 活动库导出为统一 JSON（一次性迁移，保留原有规则标签）。

用法：
    python tools/import_legacy.py --db ../wenxiang-website/data/wenxiang.db \
        --out data/raw/activities.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xian_activities.models import Activity  # noqa: E402


def load_rows(db_path: Path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    rows = [dict(row) for row in connection.execute("select * from activities order by id")]
    connection.close()
    return rows


def parse_json_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        parsed = json.loads(value)
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def source_of(row: dict) -> str:
    source = (row.get("source") or "").strip()
    if source:
        return source
    link = row.get("guide_link") or ""
    if "snpac" in link:
        return "陕西大剧院"
    if "bendibao" in link:
        return "西安本地宝"
    return "西安公共文化场馆目录"


def convert(row: dict) -> Activity:
    tags = {
        "categories": parse_json_list(row.get("activity_type_tags")),
        "demand": parse_json_list(row.get("demand_tags")),
        "comfort": [row["comfort_tag"]] if row.get("comfort_tag") else [],
        "factors": parse_json_list(row.get("factor_tags")),
        "age_fit": parse_json_list(row.get("age_fit_tags")),
        "time_slots": parse_json_list(row.get("time_slot_tags")),
        "themes": [],
        "moods": [],
        "audience": [],
    }
    return Activity(
        name=row.get("name") or "",
        source=source_of(row),
        source_id=str(row.get("source_id") or "").removesuffix(".0"),
        category_text=row.get("type") or "",
        time_text=row.get("time") or "",
        address=row.get("address") or "",
        price_text=row.get("price") or "",
        price_level=row.get("price_level") or "unknown",
        highlights=row.get("highlights") or "",
        link=row.get("guide_link") or "",
        valid_start=row.get("valid_start"),
        valid_end=row.get("valid_end"),
        tags=tags,
        scores={"transport": float(row.get("transport_score") or 0.5)},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="历史 wenxiang.db 路径")
    parser.add_argument("--out", default=str(ROOT / "data" / "raw" / "activities.json"))
    args = parser.parse_args()

    rows = load_rows(Path(args.db))
    activities = [convert(row) for row in rows if (row.get("name") or "").strip()]
    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source": "legacy-sqlite",
        "count": len(activities),
        "activities": [activity.to_dict() for activity in activities],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已导出 {len(activities)} 条活动 -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
