# -*- coding: utf-8 -*-
"""命令行入口：

    python -m xian_activities.cli build --limit 5      # 语义增强并生成 activities.json
    python -m xian_activities.cli check               # 检查 API 连通性
    python -m xian_activities.cli serve               # 启动 API 服务
    python -m xian_activities.cli crawl --out ...     # 抓取（需要本地浏览器）
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_build(args: argparse.Namespace) -> int:
    from .pipeline import BUILD_PATH, RAW_PATH, build

    out = Path(args.out) if args.out else BUILD_PATH
    activities, stats = build(
        raw_path=Path(args.raw) if args.raw else RAW_PATH,
        out_path=out,
        limit=args.limit,
        use_llm=not args.offline,
        use_cache=not args.no_cache,
        offline=args.offline,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"✅ 已生成 {len(activities)} 条 -> {out}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    from .llm import DeepSeekClient

    client = DeepSeekClient()
    result = client.ping()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    reply = client.chat([{"role": "user", "content": "只回复：连通正常"}], max_tokens=32)
    print("对话测试:", reply.strip())
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import app
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def cmd_crawl(args: argparse.Namespace) -> int:
    from .sources import crawl_all

    activities, report = crawl_all(args.source)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        from .export import write_json

        write_json(activities, Path(args.out))
        print(f"✅ 原始数据 -> {args.out}")
    return 0 if activities else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xian-activities", description="西安公共文化活动数据与智能推荐工具")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="语义增强并生成站点数据")
    build.add_argument("--raw", help="原始 JSON 路径")
    build.add_argument("--out", help="输出 JSON 路径")
    build.add_argument("--limit", type=int, help="只处理前 N 条（调试用）")
    build.add_argument("--offline", action="store_true", help="不调用 LLM，仅规则清洗")
    build.add_argument("--no-cache", action="store_true", help="忽略本地缓存")
    build.set_defaults(func=cmd_build)

    check = sub.add_parser("check", help="检查 DeepSeek API 连通性")
    check.set_defaults(func=cmd_check)

    serve = sub.add_parser("serve", help="启动 HTTP 服务")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=cmd_serve)

    crawl = sub.add_parser("crawl", help="抓取活动（需要本地 Chrome/Edge）")
    crawl.add_argument("--source", default="all")
    crawl.add_argument("--out")
    crawl.set_defaults(func=cmd_crawl)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
