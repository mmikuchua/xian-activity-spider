# -*- coding: utf-8 -*-
"""运行时配置：全部来自环境变量，密钥永不落盘到代码库里。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """极简 .env 读取（不引入 python-dotenv 依赖）。已存在的环境变量优先。"""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    # 打标用便宜快的模型；面向用户的顾问/解释用更强的模型
    tag_model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_TAG_MODEL", "deepseek-flash"))
    chat_model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-flash"))
    timeout: float = field(default_factory=lambda: float(os.getenv("DEEPSEEK_TIMEOUT", "120")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("DEEPSEEK_MAX_RETRIES", "3")))
    concurrency: int = field(default_factory=lambda: int(os.getenv("ENRICH_CONCURRENCY", "4")))
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("ENRICH_CACHE_DIR", str(ROOT / ".cache" / "enrich"))))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", str(ROOT / "data"))))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    allow_crawl: bool = field(default_factory=lambda: os.getenv("ALLOW_CRAWL", "true").lower() == "true")
    cors_origins: str = field(default_factory=lambda: os.getenv("CORS_ORIGINS", "*"))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.api_key)

    def require_llm(self) -> None:
        if not self.llm_enabled:
            raise RuntimeError(
                "未配置 DEEPSEEK_API_KEY。请复制 .env.example 为 .env 并填入密钥，"
                "或设置同名环境变量后再运行。"
            )


settings = Settings()
