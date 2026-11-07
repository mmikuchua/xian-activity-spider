# -*- coding: utf-8 -*-
"""活动数据 + AI 推荐 HTTP 服务。

    uvicorn xian_activities.server:app --port 8000

主要端点：
    GET  /api/health                 健康检查（含模型连通性开关）
    GET  /api/activities             活动列表，支持 q/limit/category/district/free
    GET  /api/activities/{id}        单条活动
    POST /api/recommend              {query, profile?, k?} → AI 排序 + 理由
    POST /api/chat                   {messages | query, profile?} → 对话式推荐
    POST /api/refresh                {sources?, enrich?} → 抓取并更新活动库（需 ALLOW_CRAWL=true）
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .advisor import Advisor, lexical_score
from .config import settings
from .models import Activity
from .pipeline import BUILD_PATH, build

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("xian_activities")

app = FastAPI(title="西安公共文化活动 · 数据与 AI 推荐 API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()] or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_lock = threading.Lock()
_cache: Dict[str, Any] = {"mtime": 0.0, "activities": [], "meta": {}, "generated_at": ""}


# --------------------------------------------------------------------- 数据
def load_activities(force: bool = False) -> List[Activity]:
    path = BUILD_PATH
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"活动数据不存在：{path}，请先运行 python -m xian_activities.cli build")
    mtime = path.stat().st_mtime
    if not force and _cache["activities"] and _cache["mtime"] == mtime:
        return _cache["activities"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    activities = [Activity.from_dict(item) for item in payload.get("activities", [])]
    _cache.update(
        {
            "mtime": mtime,
            "activities": activities,
            "meta": payload.get("meta") or {},
            "generated_at": payload.get("generated_at") or "",
        }
    )
    return activities


def _advisor() -> Advisor:
    return Advisor(load_activities())


# --------------------------------------------------------------------- 模型
class RecommendRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    profile: Dict[str, Any] = Field(default_factory=dict)
    k: int = Field(5, ge=1, le=10)
    use_llm: bool = True


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: Optional[List[ChatMessage]] = None
    query: Optional[str] = None
    profile: Dict[str, Any] = Field(default_factory=dict)


class RefreshRequest(BaseModel):
    sources: str = "all"
    enrich: bool = True
    limit: Optional[int] = None


# --------------------------------------------------------------------- API
@app.get("/")
def home() -> Dict[str, Any]:
    return {
        "service": "xian-activities",
        "version": app.version,
        "docs": "/docs",
        "endpoints": ["/api/health", "/api/activities", "/api/recommend", "/api/chat", "/api/refresh"],
    }


@app.get("/api/health")
def health() -> Dict[str, Any]:
    try:
        activities = load_activities()
        ready = True
    except HTTPException:
        activities = []
        ready = False
    return {
        "status": "ok" if ready else "degraded",
        "service": "xian-activities",
        "version": app.version,
        "llm": settings.llm_enabled,
        "tag_model": settings.tag_model,
        "chat_model": settings.chat_model,
        "activities": len(activities),
        "generated_at": _cache.get("generated_at", ""),
        "time": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


@app.get("/api/activities")
def list_activities(
    q: str = "",
    limit: int = 50,
    category: str = "",
    district: str = "",
    free: bool = False,
) -> Dict[str, Any]:
    activities = load_activities()
    result = activities
    if category:
        result = [item for item in result if category.upper() in item.tags.get("categories", [])]
    if district:
        result = [item for item in result if district in (item.district or "")]
    if free:
        result = [item for item in result if item.price_level == "free"]
    if q:
        result = sorted(result, key=lambda item: -lexical_score(q, item))[: max(1, min(limit, 200))]
        payload = [item.to_dict() | {"score": lexical_score(q, item)} for item in result]
    else:
        result = result[: max(1, min(limit, 200))]
        payload = [item.to_dict() for item in result]
    return {"count": len(payload), "total": len(activities), "activities": payload}


@app.get("/api/activities/{activity_id}")
def get_activity(activity_id: str) -> Dict[str, Any]:
    for activity in load_activities():
        if activity.id == activity_id:
            return activity.to_dict()
    raise HTTPException(status_code=404, detail="活动不存在")


@app.post("/api/recommend")
def recommend(request: RecommendRequest) -> Dict[str, Any]:
    advisor = _advisor()
    result = advisor.recommend(request.query, request.profile, k=request.k, use_llm=request.use_llm)
    return {
        "reply": result.reply,
        "used_llm": result.used_llm,
        "latency_ms": result.latency_ms,
        "items": [
            {**pick["activity"].to_dict(), "reason": pick["reason"], "rank": index + 1}
            for index, pick in enumerate(result.picks)
        ],
    }


@app.post("/api/chat")
def chat(request: ChatRequest) -> Dict[str, Any]:
    """对话式推荐：取最后一条用户消息作为需求，返回可渲染的活动卡片。"""
    query = request.query or ""
    if not query and request.messages:
        query = next((message.content for message in reversed(request.messages) if message.role == "user"), "")
    if not query:
        raise HTTPException(status_code=400, detail="缺少 query 或 messages 中的用户消息")

    advisor = _advisor()
    result = advisor.recommend(query, request.profile, k=4)
    return {
        "reply": result.reply,
        "activity_ids": result.ids(),
        "used_llm": result.used_llm,
        "items": [
            {
                "id": pick["activity"].id,
                "name": pick["activity"].name,
                "district": pick["activity"].district,
                "price_level": pick["activity"].price_level,
                "reason": pick["reason"],
            }
            for pick in result.picks
        ],
    }


@app.get("/api/stats")
def stats() -> Dict[str, Any]:
    activities = load_activities()
    from collections import Counter

    categories: Counter = Counter()
    districts: Counter = Counter()
    prices: Counter = Counter()
    for activity in activities:
        categories.update(activity.tags.get("categories", []))
        districts.update([activity.district or "未知"])
        prices.update([activity.price_level])
    return {
        "count": len(activities),
        "categories": dict(categories),
        "districts": dict(districts.most_common(15)),
        "price_levels": dict(prices),
        "generated_at": _cache.get("generated_at", ""),
    }


@app.post("/api/refresh")
async def refresh(request: RefreshRequest) -> Dict[str, Any]:
    """抓取 + 语义增强，重新生成 activities.json。

    浏览器抓取可能被人机验证拦截，因此即使失败也会返回已有数据状态。
    """
    if not settings.allow_crawl:
        raise HTTPException(status_code=403, detail="服务端已禁用抓取（ALLOW_CRAWL=false）")

    def _run() -> Dict[str, Any]:
        from .sources import crawl_all

        started = time.time()
        activities, report = crawl_all(request.sources, limit=request.limit)
        if not activities:
            return {"ok": False, "stage": "crawl", "report": report, "duration_s": round(time.time() - started, 1)}
        raw_path = Path(settings.data_dir) / "raw" / "activities.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                    "source": "crawl",
                    "count": len(activities),
                    "activities": [item.to_dict() for item in activities],
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        if not request.enrich:
            return {"ok": True, "stage": "crawl", "report": report, "raw": str(raw_path)}
        _, build_stats = build(raw_path=raw_path, out_path=BUILD_PATH, use_llm=settings.llm_enabled)
        load_activities(force=True)
        return {"ok": True, "stage": "build", "report": report, "build": build_stats}

    started = time.time()
    report = await run_in_threadpool(_run)
    return {**report, "duration_s": round(time.time() - started, 1)}
