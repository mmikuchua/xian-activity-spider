# -*- coding: utf-8 -*-
"""轻量 HTTP 工具：标准库实现，带重试、超时与编码兜底。

选择 urllib 而不是 requests，是为了让 CI 里只装 beautifulsoup4 就能跑抓取。
"""

from __future__ import annotations

import gzip
import json
import logging
import random
import time
import urllib.error
import urllib.request
import zlib
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "identity",
}


class FetchError(RuntimeError):
    pass


def _decode(raw: bytes, charset: Optional[str]) -> str:
    if charset:
        try:
            return raw.decode(charset, "ignore")
        except LookupError:
            pass
    for candidate in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(candidate)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def _decompress(raw: bytes, encoding: str) -> bytes:
    if encoding == "gzip":
        return gzip.decompress(raw)
    if encoding == "deflate":
        return zlib.decompress(raw)
    return raw


def get(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 25,
    retries: int = 2,
    charset: Optional[str] = None,
) -> str:
    merged = {**DEFAULT_HEADERS, **(headers or {})}
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers=merged)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                raw = _decompress(raw, (response.headers.get("Content-Encoding") or "").lower())
                return _decode(raw, charset or response.headers.get_content_charset())
        except urllib.error.HTTPError as exc:
            last_error = FetchError(f"HTTP {exc.code}: {url}")
            if exc.code in (403, 404, 410):
                break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = FetchError(f"网络异常: {exc} ({url})")
        if attempt < retries:
            time.sleep(min(2 ** attempt, 6) + random.random())
    raise last_error or FetchError(f"请求失败: {url}")


def get_json(url: str, **kwargs: Any) -> Any:
    text = get(url, **kwargs)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        head = text.strip()[:120].replace("\n", " ")
        raise FetchError(f"返回内容不是 JSON（可能触发了人机验证）：{head}") from exc
