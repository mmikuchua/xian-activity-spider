# -*- coding: utf-8 -*-
"""LLM 语义增强：把「标题 + 简介」这类弱结构数据，转成推荐引擎能吃的画像标签。

相比原来的关键词字典，这一层能处理三类关键词规则搞不定的情况：
1. 同义词/行话（"遛娃"、"研学"、"沉浸式"）；
2. 一处活动同时服务多个人群（一场秦腔演出既适合老年票友也适合亲子体验）；
3. 需要判断「适合谁」「值不值得去」的语义判断（quality）。
"""

from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import Settings, settings as default_settings
from .llm import DeepSeekClient, LLMError, get_client
from .models import Activity, merge_tags, clean_text
from .taxonomy import AGES, CATEGORIES, COMFORTS, DEMANDS, DISTRICTS, FACTORS, PRICE_LEVELS, TIME_SLOTS, taxonomy_prompt_block

logger = logging.getLogger(__name__)

PROMPT_VERSION = "2026-11-tag-v1"
BATCH_SIZE = 6

SYSTEM_PROMPT = f"""你是西安公共文化服务平台的资深内容运营与推荐算法标注员。
你的任务：把每个文化活动/场馆，标注成推荐引擎可用的画像标签。

严格的编码体系（只能使用这些编码）：
{taxonomy_prompt_block()}

标注原则：
- 站在「真实去参加的人」的角度判断：这场活动解决了什么需求、适合什么人、什么时间去得了。
- 一次活动最多 3 个 categories；demand/comfort/factors 各 1-2 个；age_fit 可多选。
- time_slots 表示「能否在该时段参加」：常设展馆、全天开放选 A、B、C；只有白天开放不要选 A（工作日晚间）。
- price_level：免费公益=free；50 元以下=low；50-200=medium；200 以上=high；信息不明=unknown。
- themes 用 3-5 个中文短词，写具体内容主题（如「秦腔」「唐文化」「自然科普」），不要写「活动」「文化」这类空词。
- moods 用 1-3 个中文词描述现场氛围（如「静心」「热闹」「浪漫」）。
- audience 用 1-3 个中文词描述主要人群（如「亲子家庭」「大学生」「银发族」「情侣」）。
- summary 不超过 40 字，客观介绍看点，不要夸张营销词，不要出现「欢迎前来」。
- scores 为 0-1 的小数，表示该属性强度：culture 文化含量、transport 交通便利（地铁/公交可达性）、
  environment 环境美感、cost 性价比（越免费越高）、family 亲子友好、quiet 安静程度、
  social 社交属性、learning 知识密度、quality 作为推荐标的的综合质量。
- 信息不足时给出保守的中间值（0.5），不要编造具体事实。

只输出 JSON，不要输出任何解释。输出结构：
{{"items":[{{"id":"原始id","categories":["C"],"demand":["A"],"comfort":["A"],
"factors":["A"],"age_fit":["B","C"],"time_slots":["A","B"],"price_level":"free",
"price_from":0,"district":"雁塔区","themes":["秦腔","非遗"],"moods":["热闹"],
"audience":["本地居民"],"summary":"...","scores":{{"culture":0.9,"transport":0.7,
"environment":0.6,"cost":1.0,"family":0.4,"quiet":0.3,"social":0.6,"learning":0.7,
"quality":0.8}}}}]}}"""


@dataclass
class EnrichResult:
    activity: Activity
    used_llm: bool
    cached: bool
    error: str = ""


def _cache_key(activity: Activity) -> str:
    payload = "|".join(
        [
            PROMPT_VERSION,
            activity.name,
            activity.category_text,
            activity.address,
            activity.price_text,
            activity.time_text,
            activity.highlights,
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def semantic_hash(activity: Activity) -> str:
    """只覆盖「语义内容」的指纹：档期/票价变了不需要重新打标。"""
    payload = "|".join(
        [PROMPT_VERSION, activity.name, activity.category_text, activity.highlights[:400]]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _clip_codes(values: Iterable[Any], allowed: Dict[str, str], limit: int) -> List[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return []
    result: List[str] = []
    for value in values:
        code = clean_text(value, 4).upper()
        if code in allowed and code not in result:
            result.append(code)
        if len(result) >= limit:
            break
    return result


def _clip_words(values: Iterable[Any], limit: int, word_limit: int = 12) -> List[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return []
    result: List[str] = []
    for value in values:
        word = clean_text(value, word_limit)
        if word and word not in result:
            result.append(word)
        if len(result) >= limit:
            break
    return result


def _clip_scores(raw: Dict[str, Any]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for key in ("culture", "transport", "environment", "cost", "family", "quiet", "social", "learning", "quality"):
        try:
            value = float(raw.get(key))  # type: ignore[union-attr]
        except (TypeError, ValueError, AttributeError):
            continue
        scores[key] = max(0.0, min(1.0, value))
    return scores


def sanitize_enrichment(raw: Dict[str, Any]) -> Dict[str, Any]:
    """把模型输出收敛到合法取值，任何越界都退回中性值。"""
    price_level = clean_text(raw.get("price_level"), 10).lower()
    if price_level not in PRICE_LEVELS:
        price_level = "unknown"

    price_from: Optional[float] = None
    try:
        if raw.get("price_from") is not None:
            price_from = max(0.0, float(raw["price_from"]))
    except (TypeError, ValueError):
        price_from = None

    district = clean_text(raw.get("district"), 12)
    if district and district not in DISTRICTS:
        # 允许返回「雁塔」这类简写
        matched = next((item for item in DISTRICTS if item.startswith(district)), "")
        district = matched

    summary = clean_text(raw.get("summary"), 60)

    return {
        "categories": _clip_codes(raw.get("categories"), CATEGORIES, 3),
        "demand": _clip_codes(raw.get("demand"), DEMANDS, 2),
        "comfort": _clip_codes(raw.get("comfort"), COMFORTS, 2),
        "factors": _clip_codes(raw.get("factors"), FACTORS, 2),
        "age_fit": _clip_codes(raw.get("age_fit"), AGES, 4),
        "time_slots": _clip_codes(raw.get("time_slots"), TIME_SLOTS, 4),
        "themes": _clip_words(raw.get("themes"), 6),
        "moods": _clip_words(raw.get("moods"), 3),
        "audience": _clip_words(raw.get("audience"), 3),
        "price_level": price_level,
        "price_from": price_from,
        "district": district,
        "summary": summary,
        "scores": _clip_scores(raw.get("scores") or {}),
    }


def completeness_score(activity: Activity) -> float:
    """没有 LLM 时的质量兜底：信息越完整越可信。"""
    checks = [
        bool(activity.address and activity.address not in ("未获取", "无")),
        bool(activity.price_text and activity.price_text not in ("未获取", "无", "待定")),
        bool(activity.time_text and activity.time_text not in ("未获取", "无")),
        len(activity.highlights) >= 30,
        bool(activity.link and activity.link not in ("无",)),
    ]
    return round(sum(1 for check in checks if check) / len(checks), 3)


def _build_user_prompt(batch: List[Activity]) -> str:
    items = []
    for activity in batch:
        items.append(
            {
                "id": activity.id,
                "name": activity.name,
                "type": activity.category_text,
                "address": activity.address,
                "district_guess": activity.district,
                "price": activity.price_text,
                "time": activity.time_text,
                "highlights": activity.highlights[:300],
            }
        )
    return (
        "请为下列活动标注，输出 JSON（items 数组，顺序与输入一致，id 必须原样返回）：\n"
        + json.dumps(items, ensure_ascii=False)
    )


class ActivityEnricher:
    def __init__(
        self,
        client: Optional[DeepSeekClient] = None,
        settings: Optional[Settings] = None,
        *,
        use_cache: bool = True,
    ) -> None:
        self.settings = settings or default_settings
        self.client = client or get_client()
        self.use_cache = use_cache
        self.cache_dir: Path = self.settings.cache_dir
        if use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ cache
    def _read_cache(self, key: str) -> Optional[Dict[str, Any]]:
        if not self.use_cache:
            return None
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _write_cache(self, key: str, value: Dict[str, Any]) -> None:
        if not self.use_cache:
            return
        try:
            (self.cache_dir / f"{key}.json").write_text(
                json.dumps(value, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:  # 缓存失败不影响主流程
            logger.warning("写入缓存失败: %s", exc)

    # ------------------------------------------------------------------- core
    def _apply(self, activity: Activity, payload: Dict[str, Any], *, model: str, cached: bool) -> Activity:
        cleaned = sanitize_enrichment(payload)
        activity.summary = cleaned["summary"] or activity.summary
        # 模型看到了名称+地址，比关键词推断更可靠，优先采用
        activity.district = cleaned["district"] or activity.district
        if cleaned["price_level"] != "unknown":
            activity.price_level = cleaned["price_level"]
        elif activity.price_level == "unknown":
            activity.price_level = cleaned["price_level"]
        if cleaned["price_from"] is not None:
            activity.price_from = cleaned["price_from"]
        elif activity.price_from is None:
            activity.price_from = None

        activity.tags = merge_tags(
            {
                "categories": cleaned["categories"],
                "demand": cleaned["demand"],
                "comfort": cleaned["comfort"],
                "factors": cleaned["factors"],
                "age_fit": cleaned["age_fit"],
                "time_slots": cleaned["time_slots"],
                "themes": cleaned["themes"],
                "moods": cleaned["moods"],
                "audience": cleaned["audience"],
            },
            activity.tags,
        )
        # 交通分保留规则侧的历史判断（基于地址与地铁关键词），与模型判断加权
        legacy_transport = activity.scores.get("transport", 0.5)
        llm_scores = cleaned["scores"]
        activity.scores.update(llm_scores)
        if "transport" in llm_scores:
            activity.scores["transport"] = round(0.5 * legacy_transport + 0.5 * llm_scores["transport"], 3)
        activity.scores.setdefault("quality", 0.5)
        activity.scores["quality"] = round(
            max(activity.scores.get("quality", 0.5), completeness_score(activity) * 0.9), 3
        )
        activity.enriched = {
            "model": model,
            "at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "version": PROMPT_VERSION,
            "cached": cached,
            "hash": semantic_hash(activity),
        }
        return activity

    def enrich_batch(self, batch: List[Activity]) -> List[EnrichResult]:
        self.settings.require_llm()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(batch)},
        ]
        data = self.client.chat_json(
            messages, model=self.settings.tag_model, temperature=0.1, max_tokens=8192
        )
        items = data.get("items")
        if not isinstance(items, list):
            raise LLMError(f"标注返回缺少 items 数组：{str(data)[:200]}")
        by_id = {clean_text(item.get("id"), 40): item for item in items if isinstance(item, dict)}

        results: List[EnrichResult] = []
        for activity in batch:
            payload = by_id.get(activity.id)
            if not payload:
                results.append(EnrichResult(activity, used_llm=False, cached=False, error="模型漏标"))
                continue
            self._write_cache(_cache_key(activity), {**payload, "_model": self.settings.tag_model})
            results.append(
                EnrichResult(
                    self._apply(activity, payload, model=self.settings.tag_model, cached=False),
                    used_llm=True,
                    cached=False,
                )
            )
        return results

    def enrich_one_cached(self, activity: Activity) -> EnrichResult:
        key = _cache_key(activity)
        cached_payload = self._read_cache(key)
        if cached_payload is not None:
            return EnrichResult(
                self._apply(activity, cached_payload, model=cached_payload.get("_model", self.settings.tag_model), cached=True),
                used_llm=True,
                cached=True,
            )
        return EnrichResult(activity, used_llm=False, cached=False, error="未命中缓存")

    def enrich_all(
        self,
        activities: List[Activity],
        *,
        progress: bool = True,
        skip_enriched: bool = True,
        max_items: Optional[int] = None,
    ) -> Tuple[List[Activity], Dict[str, Any]]:
        """批量增强：已标注且内容未变的直接跳过，其余先吃缓存再并发送 LLM。"""
        self.settings.require_llm()
        pending: List[Activity] = []
        cache_hits = 0
        skipped = 0
        for activity in activities:
            if (
                skip_enriched
                and activity.enriched.get("model")
                and activity.enriched.get("hash") == semantic_hash(activity)
            ):
                skipped += 1
                continue
            key = _cache_key(activity)
            cached_payload = self._read_cache(key)
            if cached_payload is not None:
                self._apply(activity, cached_payload, model=cached_payload.get("_model", self.settings.tag_model), cached=True)
                cache_hits += 1
            else:
                pending.append(activity)

        if max_items is not None and len(pending) > max_items:
            logger.warning("本次只标注前 %s 条，剩余 %s 条留到下次", max_items, len(pending) - max_items)
            pending = pending[:max_items]

        batches = [pending[i : i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
        failures: List[str] = []
        done = 0

        if batches:
            with ThreadPoolExecutor(max_workers=max(1, self.settings.concurrency)) as pool:
                futures = {pool.submit(self.enrich_batch, batch): batch for batch in batches}
                for future in as_completed(futures):
                    batch = futures[future]
                    done += len(batch)
                    try:
                        results = future.result()
                        for result in results:
                            if result.error:
                                failures.append(f"{result.activity.name}:{result.error}")
                    except Exception as exc:  # noqa: BLE001 - 单批失败不拖垮全流程
                        failures.append(f"批次失败: {exc}")
                        logger.warning("批次标注失败：%s", exc)
                    if progress:
                        logger.info("语义标注进度 %s/%s", done, len(pending))

        stats = {
            "total": len(activities),
            "skipped": skipped,
            "cache_hits": cache_hits,
            "pending": len(pending),
            "llm_calls": self.client.usage.calls,
            "failures": failures[:10],
            "failed_count": len(failures),
            "usage": self.client.usage.as_dict(),
        }
        return activities, stats

    @staticmethod
    def _payload_of(activity: Activity) -> Dict[str, Any]:
        return {
            "categories": activity.tags.get("categories", []),
            "demand": activity.tags.get("demand", []),
            "comfort": activity.tags.get("comfort", []),
            "factors": activity.tags.get("factors", []),
            "age_fit": activity.tags.get("age_fit", []),
            "time_slots": activity.tags.get("time_slots", []),
            "themes": activity.tags.get("themes", []),
            "moods": activity.tags.get("moods", []),
            "audience": activity.tags.get("audience", []),
            "price_level": activity.price_level,
            "price_from": activity.price_from,
            "district": activity.district,
            "summary": activity.summary,
            "scores": activity.scores,
        }
