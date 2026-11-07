# -*- coding: utf-8 -*-
"""统一的活动数据模型。

站点的推荐引擎（web/assets/js/engine.js）和这里的 Python 流水线共用同一份
JSON 结构，字段见 README「数据结构」一节。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .taxonomy import CATEGORIES, DISTRICTS, PRICE_LEVELS

SCHEMA_VERSION = 2


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def clean_text(value: Any, limit: int = 600) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(clean_text(item, limit) for item in value)
    text = str(value)
    # 只清理零宽字符与多余空白，保留中文全角标点
    text = re.sub(r"[\u200b-\u200f\uFEFF]", "", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text).strip()
    return text[:limit]


def slug_id(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"act-{digest}"


_TITLE_PREFIX = re.compile(
    r"^(?:\d{1,2}\s*[./月]\s*\d{1,2}\s*日?\s*(?:周[一二三四五六日天]|上午|下午|晚上)?\s*[|｜丨]?\s*)+"
)
_TITLE_SUFFIX = re.compile(r"[（(]\s*下滑阅读(?:活动)?详情\s*[）)]")
_TITLE_CITY = re.compile(r"^(?:【西安】|西安\s*[|｜丨]\s*)")
_TITLE_LEAD = re.compile(r"^(?:上午|下午|晚上|周六|周日|周末)\s*")


def clean_title(name: str) -> str:
    """去掉活动行/豆瓣标题里的日期前缀和运营后缀，保留内容本身。"""
    text = clean_text(name, 160)
    for _ in range(3):
        before = text
        text = _TITLE_CITY.sub("", text)
        text = _TITLE_PREFIX.sub("", text)
        text = _TITLE_LEAD.sub("", text)
        text = _TITLE_SUFFIX.sub("", text)
        text = text.strip(" |｜丨-—")
        if text == before:
            break
    return text or clean_text(name, 160)


_PRICE_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)")


def normalize_price_level(price_text: str, raw_level: str = "") -> str:
    """把各种价格文案归一为 free / low / medium / high / unknown。"""
    level = (raw_level or "").strip().lower()
    if level in PRICE_LEVELS and level != "unknown":
        return level
    text = clean_text(price_text).lower()
    if not text or text in ("未获取", "暂无", "无", "待定"):
        return "unknown"
    free_pattern = r"(免费|公益|惠民|免票|不收费|不花钱|无需门票)"
    # 注意 "30元" / "680元" 里也含 "0元"，必须加左边界
    if re.search(free_pattern, text) or re.search(r"(?<!\d)0\s*元", text):
        return "free"
    numbers = [float(n) for n in _PRICE_NUM_RE.findall(text)]
    if not numbers:
        return "unknown"
    value = max(numbers)
    if value <= 0:
        return "free"
    if value < 50:
        return "low"
    if value <= 200:
        return "medium"
    return "high"


def price_from_text(price_text: str) -> Optional[float]:
    text = clean_text(price_text)
    if "免费" in text or "公益" in text:
        return 0.0
    numbers = [float(n) for n in _PRICE_NUM_RE.findall(text)]
    return min(numbers) if numbers else None


def infer_district(address: str) -> str:
    text = clean_text(address)
    # 1) 先认地标：避免「长安路」被误判成「长安区」
    landmarks = {
        "大雁塔": "雁塔区", "小雁塔": "碑林区", "钟楼": "碑林区", "城墙": "碑林区",
        "大唐不夜城": "雁塔区", "曲江": "曲江新区", "高新": "高新区", "浐灞": "浐灞生态区",
        "兵马俑": "临潼区", "华清宫": "临潼区", "大明宫": "新城区", "未央": "未央区",
        "碑林": "碑林区", "莲湖": "莲湖区", "新城": "新城区", "灞桥": "灞桥区",
        "阎良": "阎良区", "高陵": "高陵区", "鄠邑": "鄠邑区", "蓝田": "蓝田县",
        "周至": "周至县", "省图": "碑林区", "陕图": "碑林区", "陕西省图书馆": "碑林区",
        "陕西历史博物馆": "雁塔区", "陕西美术博物馆": "碑林区", "西安博物院": "碑林区",
        "西安音乐厅": "雁塔区", "陕西大剧院": "雁塔区", "西安图书馆": "未央区",
    }
    for keyword, district in landmarks.items():
        if keyword in text:
            return district
    # 2) 再认完整的行政区名
    for district in DISTRICTS:
        if district in text:
            return district
    # 3) 最后才用简称，且排除常见路名干扰
    for district in DISTRICTS:
        short = district.replace("区", "").replace("县", "")
        if short and short in text and not re.search(short + r"[路街巷]", text):
            return district
    return ""


@dataclass
class Activity:
    name: str
    id: str = ""
    source: str = ""
    source_id: str = ""
    category_text: str = ""
    summary: str = ""
    time_text: str = ""
    address: str = ""
    district: str = ""
    price_text: str = ""
    price_level: str = "unknown"
    price_from: Optional[float] = None
    highlights: str = ""
    link: str = ""
    cover: str = ""
    tags: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "categories": [],
            "demand": [],
            "comfort": [],
            "factors": [],
            "age_fit": [],
            "time_slots": [],
            "themes": [],
            "moods": [],
            "audience": [],
        }
    )
    scores: Dict[str, float] = field(
        default_factory=lambda: {
            "culture": 0.5,
            "transport": 0.5,
            "environment": 0.5,
            "cost": 0.5,
            "family": 0.5,
            "quiet": 0.5,
            "social": 0.5,
            "learning": 0.5,
            "quality": 0.5,
        }
    )
    valid_start: Optional[str] = None
    valid_end: Optional[str] = None
    enriched: Dict[str, Any] = field(default_factory=dict)
    seen_at: str = ""

    # ------------------------------------------------------------------ 构造
    def __post_init__(self) -> None:
        self.name = clean_text(self.name, 160)
        self.category_text = clean_text(self.category_text, 120)
        self.summary = clean_text(self.summary, 200)
        self.time_text = clean_text(self.time_text, 200)
        self.address = clean_text(self.address, 240)
        self.price_text = clean_text(self.price_text, 160)
        self.highlights = clean_text(self.highlights, 800)
        self.link = clean_text(self.link, 500)
        if not self.district:
            self.district = infer_district(self.address)
        if self.price_level not in PRICE_LEVELS or self.price_level == "unknown":
            self.price_level = normalize_price_level(self.price_text)
        if self.price_from is None:
            self.price_from = price_from_text(self.price_text)
        if not self.id:
            self.id = slug_id(self.source or "seed", self.name, self.address)

    # ------------------------------------------------------------------ 序列化
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["tags"] = {key: list(dict.fromkeys(value)) for key, value in self.tags.items()}
        data["scores"] = {key: round(float(value), 3) for key, value in self.scores.items()}
        if self.price_from is not None:
            data["price_from"] = round(float(self.price_from), 2)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Activity":
        known = {field_name for field_name in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        payload = {key: value for key, value in data.items() if key in known}
        tags = payload.get("tags") or {}
        valid = data.get("valid") or {}
        payload.setdefault("valid_start", valid.get("start"))
        payload.setdefault("valid_end", valid.get("end"))
        activity = cls(**payload)
        merged = activity.tags
        for key in merged:
            value = tags.get(key) or []
            if isinstance(value, str):
                value = [value]
            merged[key] = [clean_text(item, 40) for item in value if clean_text(item, 40)]
        for key, value in (data.get("scores") or {}).items():
            if key in activity.scores:
                try:
                    activity.scores[key] = max(0.0, min(1.0, float(value)))
                except (TypeError, ValueError):
                    continue
        return activity

    # ------------------------------------------------------------------ 校验
    def validate(self) -> List[str]:
        problems: List[str] = []
        if not self.name:
            problems.append("缺少活动名称")
        if self.price_level not in PRICE_LEVELS:
            problems.append("price_level 非法")
        for key, allowed in (("categories", CATEGORIES),):
            for code in self.tags.get(key, []):
                if code not in allowed:
                    problems.append(f"{key} 含未知编码 {code}")
        return problems

    @property
    def key(self) -> str:
        """去重用的稳定键：名称 + 地址（忽略标点与大小写差异）。"""
        return re.sub(r"[\s\-—_·・,，。.!！?？()（）\[\]【】]", "", self.name + self.address).lower()

    def search_text(self) -> str:
        parts = [
            self.name,
            self.category_text,
            self.summary,
            self.highlights,
            self.address,
            " ".join(self.tags.get("themes", [])),
            " ".join(self.tags.get("audience", [])),
            " ".join(self.tags.get("moods", [])),
        ]
        return " ".join(part for part in parts if part)


def merge_tags(primary: Dict[str, List[str]], fallback: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """LLM 标签优先，缺失时回落到规则标签。"""
    merged: Dict[str, List[str]] = {}
    for key in set(primary) | set(fallback):
        values = [value for value in (primary.get(key) or []) if value]
        if not values:
            values = [value for value in (fallback.get(key) or []) if value]
        merged[key] = list(dict.fromkeys(values))
    return merged


def dedupe(activities: List[Activity]) -> List[Activity]:
    seen: Dict[str, Activity] = {}
    order: List[str] = []
    for activity in activities:
        if activity.key in seen:
            existing = seen[activity.key]
            # 保留信息更完整的一条
            if len(activity.search_text()) > len(existing.search_text()):
                seen[activity.key] = activity
            continue
        seen[activity.key] = activity
        order.append(activity.key)
    return [seen[key] for key in order]
