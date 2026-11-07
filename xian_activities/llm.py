# -*- coding: utf-8 -*-
"""DeepSeek Chat Completions 客户端（零第三方依赖，便于在任意环境跑）。

只做三件事：重试、JSON 解析兜底、token 记账。
"""

from __future__ import annotations

import json
import logging
import random
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import Settings, settings as default_settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0

    def add(self, raw: Dict[str, Any]) -> None:
        self.calls += 1
        self.prompt_tokens += int(raw.get("prompt_tokens") or 0)
        self.completion_tokens += int(raw.get("completion_tokens") or 0)
        details = raw.get("completion_tokens_details") or {}
        self.reasoning_tokens += int(details.get("reasoning_tokens") or 0)

    def as_dict(self) -> Dict[str, int]:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
        }


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_json_object(text: str) -> Dict[str, Any]:
    """尽最大努力从模型输出中取出一个 JSON 对象。"""
    cleaned = _strip_code_fence(text)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            raise LLMError(f"模型未返回 JSON：{text[:200]}")
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise LLMError(f"期望 JSON 对象，得到 {type(value).__name__}")
    return value


class DeepSeekClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or default_settings
        self.usage = Usage()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ HTTP
    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            request = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Authorization": f"Bearer {self.settings.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.settings.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:  # 4xx/5xx
                detail = exc.read().decode("utf-8", "ignore")[:400]
                last_error = LLMError(f"HTTP {exc.code}: {detail}")
                if exc.code in (400, 401, 403, 404):
                    raise last_error from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = LLMError(f"网络异常: {exc}")
            if attempt < self.settings.max_retries:
                sleep_for = min(2 ** attempt, 8) + random.random()
                logger.warning("LLM 调用失败（第 %s 次），%.1fs 后重试: %s", attempt, sleep_for, last_error)
                time.sleep(sleep_for)
        raise last_error or LLMError("未知 LLM 错误")

    # ------------------------------------------------------------------ chat
    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        self.settings.require_llm()
        payload: Dict[str, Any] = {
            "model": model or self.settings.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        data = self._post(payload)
        if "choices" not in data or not data["choices"]:
            raise LLMError(f"意外的响应：{str(data)[:300]}")
        with self._lock:
            self.usage.add(data.get("usage") or {})
        return (data["choices"][0].get("message") or {}).get("content") or ""

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> Dict[str, Any]:
        text = self.chat(
            messages,
            model=model,
            json_mode=True,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return parse_json_object(text)

    # --------------------------------------------------------------- helpers
    def ping(self) -> Dict[str, Any]:
        """连通性自检，返回模型列表与延迟。"""
        url = self.settings.base_url.rstrip("/") + "/models"
        request = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self.settings.api_key}"}
        )
        started = time.time()
        with urllib.request.urlopen(request, timeout=self.settings.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {
            "ok": True,
            "latency_ms": int((time.time() - started) * 1000),
            "models": [item.get("id") for item in data.get("data", [])],
        }


_client_lock = threading.Lock()
_shared_client: Optional[DeepSeekClient] = None


def get_client() -> DeepSeekClient:
    global _shared_client
    with _client_lock:
        if _shared_client is None:
            _shared_client = DeepSeekClient()
        return _shared_client
