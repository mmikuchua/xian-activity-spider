# -*- coding: utf-8 -*-
"""西安本地宝 · 活动日历（HTTP JSON 版）。

列表页背后有一个 `action=get_data` 的接口，返回结构化 JSON：
活动名、场馆、档期时间戳、购票平台、海报。比每次开浏览器点“展开更多”稳定得多。

注意：站点有拼图人机验证，机房 IP 可能被挡。被挡时会抛 `FetchError`，
上层会保留旧数据；本机可以用 `sources.bendibao`（Selenium）兜底。
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

from ..dates import parse_timestamp
from ..http import FetchError, get_json
from ..models import Activity

logger = logging.getLogger(__name__)

SOURCE = "西安本地宝"
API_URL = "https://xa.bendibao.com/xiuxian/huodongrili/"
PAGE_SIZE = 20
MAX_PAGES = int(os.getenv("BENDIBAO_PAGES", "3"))


def _activity_type_name(payload: Dict[str, Any], type_id: str) -> str:
    table = payload.get("activity_type") or {}
    if isinstance(table, dict):
        entry = table.get(str(type_id))
        if isinstance(entry, dict):
            return str(entry.get("name") or entry.get("title") or "")
        if isinstance(entry, str):
            return entry
    if isinstance(table, list):
        for entry in table:
            if isinstance(entry, dict) and str(entry.get("id")) == str(type_id):
                return str(entry.get("name") or "")
    return ""


def parse_payload(payload: Dict[str, Any]) -> List[Activity]:
    venues = payload.get("venue_info") or {}
    activities: List[Activity] = []
    for item in payload.get("res") or []:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        venue = venues.get(str(item.get("venue_id"))) or {}
        address = (venue.get("address") or "").strip()
        venue_name = (venue.get("name") or "").strip()
        if venue_name and venue_name not in address:
            address = f"{venue_name}（{address}）" if address else venue_name

        dates = item.get("dates") or {}
        starts, ends = [], []
        for entry in dates.values():
            if not isinstance(entry, dict):
                continue
            start = parse_timestamp(entry.get("start_date"))
            end = parse_timestamp(entry.get("end_date"))
            if start:
                starts.append(start)
            if end:
                ends.append(end)
        # 常设/长期活动 end_date 常为 0，此时不设结束时间
        valid_start = min(starts) if starts else None
        valid_end = max(ends) if ends else None
        if not valid_start:
            valid_start = parse_timestamp(item.get("earlies_day"))

        highlight = (item.get("heighlight") or "").strip()
        link = (item.get("pcurl") or "").replace("http://", "https://")
        time_text = ""
        if dates:
            first = next(iter(dates.values()))
            if isinstance(first, dict):
                time_text = first.get("time_str") or first.get("start_date_str") or ""

        activities.append(
            Activity(
                name=name,
                source=SOURCE,
                source_id=str(item.get("id") or ""),
                category_text=_activity_type_name(payload, str(item.get("type_id") or "")),
                time_text=time_text,
                address=address or "西安",
                price_text="",
                highlights=highlight,
                link=link,
                cover=item.get("image") or "",
                valid_start=valid_start,
                valid_end=valid_end,
            )
        )
    return activities


def fetch(limit: Optional[int] = None) -> List[Activity]:
    headers = {
        "Referer": API_URL,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    activities: List[Activity] = []
    for page in range(1, MAX_PAGES + 1):
        url = (
            f"{API_URL}?search=&action=get_data&page={page}&pagesize={PAGE_SIZE}"
            "&type_id1=&type_id2=&active_date_filter=&start_date=&end_date="
        )
        try:
            payload = get_json(url, headers=headers, retries=2, timeout=30)
        except FetchError as exc:
            if page == 1:
                raise RuntimeError(f"bendibao_http: 接口被拦截或返回异常（{exc}）") from exc
            break
        if not isinstance(payload, dict) or "res" not in payload:
            raise RuntimeError("bendibao_http: 返回结构异常")
        page_items = parse_payload(payload)
        activities.extend(page_items)
        logger.info("bendibao_http: 第 %s 页 %s 条", page, len(page_items))
        if not payload.get("has_more") or not page_items:
            break
        time.sleep(1.5)
    if not activities:
        raise RuntimeError("bendibao_http: 未解析到任何活动")
    return activities[:limit] if limit else activities
