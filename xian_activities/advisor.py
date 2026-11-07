# -*- coding: utf-8 -*-
"""AI 顾问：本地召回 + 大模型重排。

为什么不是「把 129 条活动全丢给模型」：
1. 全量上下文又慢又贵，而且模型容易漏 id；
2. 先用便宜的字符 n-gram 召回 25 条，再让模型在候选里做语义判断，
   既保留大模型对「遛娃」「出片」这类模糊表达的理解，又控制成本。

没有 API Key 或调用失败时，退化为「召回分 + 显式标签规则」，接口不会挂。
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .config import Settings, settings as default_settings
from .llm import DeepSeekClient, LLMError
from .models import Activity
from .taxonomy import AGES, CATEGORIES, COMFORTS, DEMANDS, FACTORS, INCOME, TIME_SLOTS, TRAFFIC

logger = logging.getLogger(__name__)

PUNCT = re.compile(r"[\s，。！？、,.!?;；:：“”\"'（）()\[\]【】\-—_/]+")

PROFILE_LABELS = {
    "age": AGES,
    "income": INCOME,
    "time": TIME_SLOTS,
    "demand": DEMANDS,
    "comfort": COMFORTS,
    "focus": FACTORS,
    "traffic": TRAFFIC,
    "actTypes": CATEGORIES,
}


def _grams(text: str) -> set[str]:
    cleaned = PUNCT.sub("", (text or "").lower())
    if len(cleaned) <= 2:
        return {cleaned} if cleaned else set()
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def _profile_text(profile: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key, table in PROFILE_LABELS.items():
        value = profile.get(key)
        if not value:
            continue
        codes = value if isinstance(value, list) else [value]
        parts.extend(table.get(str(code), "") for code in codes)
    return " ".join(part for part in parts if part)


def lexical_score(query: str, activity: Activity) -> float:
    """字符 bigram 覆盖率 + 直接命中标题/主题的加成。"""
    query_grams = _grams(query)
    if not query_grams:
        return 0.0
    doc_grams = _grams(activity.search_text())
    if not doc_grams:
        return 0.0
    overlap = len(query_grams & doc_grams)
    base = overlap / math.sqrt(len(query_grams)) / math.sqrt(max(1, len(doc_grams) / 8))
    boost = 0.0
    if activity.name and activity.name in query:
        boost += 0.8
    for theme in activity.tags.get("themes", []):
        if theme and theme in query:
            boost += 0.15
    for word in ("免费", "亲子", "讲座", "展览", "演出", "公园", "书店", "非遗"):
        if word in query and (word in activity.search_text() or word in activity.name):
            boost += 0.05
    return round(base * 3 + boost, 4)


@dataclass
class AdvisorResult:
    reply: str
    picks: List[Dict[str, Any]] = field(default_factory=list)
    used_llm: bool = False
    latency_ms: int = 0

    def ids(self) -> List[str]:
        return [item["id"] for item in self.picks]


class Advisor:
    def __init__(
        self,
        activities: Sequence[Activity],
        *,
        client: Optional[DeepSeekClient] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.activities = list(activities)
        self.settings = settings or default_settings
        self.client = client or DeepSeekClient(self.settings)

    # ------------------------------------------------------------------ 召回
    def recall(self, query: str, profile: Optional[Dict[str, Any]] = None, k: int = 25) -> List[Activity]:
        profile = profile or {}
        profile_text = _profile_text(profile)
        scored: List[tuple[float, Activity]] = []
        for activity in self.activities:
            score = lexical_score(query, activity)
            if profile_text:
                score += 0.02 * lexical_score(profile_text, activity)
            # 轻量的画像硬偏好（不改变语义判断，只影响召回顺序）
            if profile.get("demand") and profile["demand"] in activity.tags.get("demand", []):
                score += 0.15
            if profile.get("actTypes"):
                wanted = set(profile["actTypes"])
                score += 0.12 * len(wanted & set(activity.tags.get("categories", [])))
            scored.append((score, activity))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [activity for _, activity in scored[:k]]

    # ------------------------------------------------------------------ 提示词
    def _catalog(self, candidates: Sequence[Activity]) -> str:
        lines = []
        for activity in candidates:
            tags = activity.tags
            lines.append(
                " | ".join(
                    [
                        activity.id,
                        activity.name,
                        activity.district or "",
                        activity.price_level,
                        "/".join(tags.get("categories", [])),
                        "/".join(tags.get("themes", [])[:3]),
                        (activity.summary or activity.highlights)[:40],
                    ]
                )
            )
        return "\n".join(lines)

    def _messages(self, query: str, profile: Dict[str, Any], candidates: Sequence[Activity], k: int) -> List[Dict[str, str]]:
        profile_bits = []
        for key, table in PROFILE_LABELS.items():
            value = profile.get(key)
            if not value:
                continue
            codes = value if isinstance(value, list) else [value]
            profile_bits.append(f"{key}={','.join(table.get(str(code), str(code)) for code in codes)}")
        profile_text = "；".join(profile_bits) or "未提供"

        system = (
            "你是西安公共文化服务平台的活动推荐顾问，熟悉本地场馆与演出。"
            "根据用户画像和一句自然语言需求，从候选活动中挑选最合适的，并给出简短理由。\n"
            "要求：\n"
            f"1. 最多挑 {k} 个，按推荐优先级排序；只能使用候选列表里出现过的 id，绝不能编造。\n"
            "2. 优先满足用户明确说出的约束（年龄、时间、预算、地点、类型）；"
            "没有明说的约束按画像推断，不要过度推测。\n"
            "3. 理由要具体到这场活动本身（例如「免费且在工作日晚间开放」），不要空话。\n"
            "4. 只输出 JSON：{\"reply\":\"一句话总体说明\",\"picks\":[{\"id\":\"act-...\",\"reason\":\"...\"}]}"
        )
        user = (
            f"用户画像：{profile_text}\n用户需求：{query}\n\n"
            f"候选活动（id | 名称 | 行政区 | 价格档 | 类型 | 主题 | 简介）：\n{self._catalog(candidates)}"
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    # ------------------------------------------------------------------ 重排
    def recommend(
        self,
        query: str,
        profile: Optional[Dict[str, Any]] = None,
        *,
        k: int = 5,
        use_llm: bool = True,
    ) -> AdvisorResult:
        started = time.time()
        profile = profile or {}
        candidates = self.recall(query, profile, k=max(20, k * 4))
        if not candidates:
            return AdvisorResult(reply="活动库里暂时没有可用数据。", latency_ms=0)

        if use_llm and self.settings.llm_enabled:
            try:
                result = self.client.chat_json(
                    self._messages(query, profile, candidates, k),
                    temperature=0.25,
                    max_tokens=1600,
                )
                picks = self._normalize_picks(result, candidates, k)
                if picks:
                    return AdvisorResult(
                        reply=str(result.get("reply") or "").strip() or "为你挑选了这几个活动。",
                        picks=picks,
                        used_llm=True,
                        latency_ms=int((time.time() - started) * 1000),
                    )
                logger.warning("模型返回的 picks 全部无效，降级到规则排序")
            except (LLMError, json.JSONDecodeError) as exc:
                logger.warning("AI 顾问调用失败，降级到规则排序：%s", exc)

        picks = [
            {"id": activity.id, "reason": self.rule_reason(activity, query, profile), "activity": activity}
            for activity in candidates[:k]
        ]
        return AdvisorResult(
            reply="按你的描述和画像，这几个活动最贴近（AI 顾问暂不可用，已使用规则排序）。",
            picks=picks,
            used_llm=False,
            latency_ms=int((time.time() - started) * 1000),
        )

    def _normalize_picks(self, result: Dict[str, Any], candidates: Sequence[Activity], k: int) -> List[Dict[str, Any]]:
        by_id = {activity.id: activity for activity in candidates}
        picks: List[Dict[str, Any]] = []
        seen = set()
        for raw in result.get("picks") or []:
            if not isinstance(raw, dict):
                continue
            activity = by_id.get(str(raw.get("id") or ""))
            if not activity or activity.id in seen:
                continue
            seen.add(activity.id)
            picks.append(
                {
                    "id": activity.id,
                    "reason": str(raw.get("reason") or "").strip()[:120] or self.rule_reason(activity, "", {}),
                    "activity": activity,
                }
            )
            if len(picks) >= k:
                break
        return picks

    # ------------------------------------------------------------------ 解释
    @staticmethod
    def rule_reason(activity: Activity, query: str, profile: Dict[str, Any]) -> str:
        bits: List[str] = []
        if activity.price_level == "free":
            bits.append("免费")
        if profile.get("actTypes") and set(profile["actTypes"]) & set(activity.tags.get("categories", [])):
            bits.append("类型对得上")
        if profile.get("demand") and profile["demand"] in activity.tags.get("demand", []):
            bits.append("符合你想要的体验")
        themes = activity.tags.get("themes", [])[:2]
        if themes:
            bits.append("主题是" + "、".join(themes))
        if activity.district:
            bits.append(activity.district)
        return "，".join(bits[:3]) or "综合匹配度较高"

    def explain(self, activity: Activity, profile: Optional[Dict[str, Any]] = None) -> str:
        if not self.settings.llm_enabled:
            return self.rule_reason(activity, "", profile or {})
        try:
            data = self.client.chat_json(
                [
                    {
                        "role": "system",
                        "content": "用一句不超过 40 字的中文，说明这个活动为什么适合该用户，不要夸张营销词。"
                        '只输出 JSON：{"reason":"..."}',
                    },
                    {
                        "role": "user",
                        "content": f"活动：{activity.name}；简介：{activity.summary}；标签：{activity.tags}；用户画像：{profile}",
                    },
                ],
                max_tokens=200,
            )
            return str(data.get("reason") or "").strip() or self.rule_reason(activity, "", profile or {})
        except LLMError:
            return self.rule_reason(activity, "", profile or {})
