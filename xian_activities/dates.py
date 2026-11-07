# -*- coding: utf-8 -*-
"""中文日期区间的解析工具。

数据源里的时间写法五花八门：
    2026年7月6日至10月11日
    11月07日 周六 19:30 ~ 11月29日 周日 19:35
    2026-11-03
统一转成 ISO 字符串，供推荐引擎判断是否过期。
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

DATE_PART = re.compile(
    r"(?:(?P<year>20\d{2})\s*[年./-]\s*)?"
    r"(?P<month>\d{1,2})\s*[月./-]\s*"
    r"(?P<day>\d{1,2})\s*日?"
    r"(?:\s*(?:周|星期)[一二三四五六日天])?"
    r"(?:\s*(?P<hour>\d{1,2})\s*[:：]\s*(?P<minute>\d{2}))?"
)
RANGE_SPLIT = re.compile(r"\s*(?:至|到|~|～|—|－|--|-)\s*")

FULL_DATE = re.compile(r"(?P<year>20\d{2})[-/.年](?P<month>\d{1,2})[-/.月](?P<day>\d{1,2})")


def _parse_part(text: str) -> Optional[datetime]:
    match = DATE_PART.search(text)
    if not match:
        return None
    year = int(match.group("year")) if match.group("year") else date.today().year
    month = int(match.group("month"))
    day = int(match.group("day"))
    hour = int(match.group("hour") or 0)
    minute = int(match.group("minute") or 0)
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


def parse_date_range(text: str, *, default_year: Optional[int] = None) -> Tuple[Optional[str], Optional[str]]:
    """返回 (start_iso, end_iso)，解析失败返回 (None, None)。"""
    cleaned = (text or "").strip()
    if not cleaned:
        return None, None

    # 纯 ISO / 斜杠日期
    if FULL_DATE.fullmatch(cleaned):
        parsed = _parse_part(cleaned)
        return (parsed.isoformat() if parsed else None), None

    parts = [part for part in RANGE_SPLIT.split(cleaned) if part.strip()]
    start = _parse_part(parts[0]) if parts else None
    end = _parse_part(parts[1]) if len(parts) > 1 else None

    explicit_year = re.search(r"20\d{2}\s*年", cleaned)
    if start and not explicit_year and default_year and start.year == date.today().year:
        start = start.replace(year=default_year)
    if start and end:
        if not re.search(r"20\d{2}\s*年", parts[1]):
            end = end.replace(year=start.year)
        if end < start:
            # 跨年，例如 12月28日至1月3日
            try:
                end = end.replace(year=end.year + 1)
            except ValueError:
                pass
    if start and not end:
        end = None
    return (
        start.isoformat(timespec="minutes") if start else None,
        end.isoformat(timespec="minutes") if end else None,
    )


def parse_timestamp(value) -> Optional[str]:
    """秒级时间戳（本地宝/豆瓣常见）→ ISO 字符串。"""
    try:
        stamp = int(float(value))
    except (TypeError, ValueError):
        return None
    if stamp <= 0:
        return None
    return datetime.fromtimestamp(stamp).isoformat(timespec="minutes")


def is_expired(valid_end: Optional[str], *, days: int = 0) -> bool:
    if not valid_end:
        return False
    try:
        end = datetime.fromisoformat(valid_end)
    except ValueError:
        return False
    return end < datetime.now() - timedelta(days=days)


def parse_month_day_range(text: str) -> Tuple[Optional[str], Optional[str]]:
    """解析「11/21 周六 ~ 11/22 周日」这类不带年份的区间。

    年份推断规则：落在过去 180 天之外的，视为下一年。
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return None, None
    matches = re.findall(r"(\d{1,2})/(\d{1,2})", cleaned)
    if not matches:
        return parse_date_range(cleaned)

    today = date.today()
    parsed: list[datetime] = []
    for month, day in matches[:2]:
        try:
            candidate = datetime(today.year, int(month), int(day))
        except ValueError:
            return None, None
        if candidate < datetime.now() - timedelta(days=180):
            try:
                candidate = candidate.replace(year=today.year + 1)
            except ValueError:
                pass
        parsed.append(candidate)
    start = parsed[0]
    end = parsed[1] if len(parsed) > 1 else None
    if end and end < start:
        try:
            end = end.replace(year=end.year + 1)
        except ValueError:
            pass
    return (
        start.isoformat(timespec="minutes") if start else None,
        end.isoformat(timespec="minutes") if end else None,
    )
