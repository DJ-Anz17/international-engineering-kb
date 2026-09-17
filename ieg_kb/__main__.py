from __future__ import annotations

import argparse
import json
import platform
import sqlite3
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict

from .answer import answer_question
from .chat_provider import status as chat_status
from .config import database_path, library_path, load_config, write_default_config
from .database import connect, initialize, stats
from .ingest import ingest_library
from .library import initialize_library
from .learning_export import export_learning_pack
from .mcp_server import run as run_mcp
from .ollama import health
from .search import search
from .web_server import run as run_web


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _filters(args: argparse.Namespace) -> Dict[str, str]:
    keys = ("document_id", "category", "country", "project", "contract_form")
    return {key: getattr(args, key, "") for key in keys if getattr(args, key, "")}


def _add_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--document-id", default="", help="只检索指定文档 ID")
    parser.add_argument("--category", default="", help="类别精确筛选")
    parser.add_argument("--country", default="", help="国别精确筛选")
    parser.add_argument("--project", default="", help="项目精确筛选")
    parser.add_argument("--contract-form", default="", help="合同范本精确筛选")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(prog="ieg-kb", description="本地国际工程个人知识库")
    parser.add_argument("--config", default=None, help="配置文件路径")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="初始化分类目录与数据库")
    ingest_parser = subparsers.add_parser("ingest", help="增量索引资料")
    ingest_parser.add_argument("--path", default=None, help="只索引知识库内的指定文件/目录")
    ingest_parser.add_argument("--force", action="store_true", help="强制重建已有文件")
    ingest_parser.add_argument("--embeddings", choices=("auto", "on", "off"), default="auto")

    search_parser = subparsers.add_parser("search", help="检索知识库")
    search_parser.add_argument("query")
    search_parser.add_argument("--top-k", type=int, default=8)
    search_parser.add_argument("--lexical-only", action="store_true")
    _add_filters(search_parser)

    ask_parser = subparsers.add_parser("ask", help="用配置的 AI 服务生成带引用的回答")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--mode", default="grounded_qa")
    ask_parser.add_argument("--top-k", type=int, default=8)
    _add_filters(ask_parser)

    serve_parser = subparsers.add_parser("serve", help="启动本地网页")
    serve_parser.add_argument("--host", default="")
    serve_parser.add_argument("--port", type=int, default=0)
    serve_parser.add_argument("--open", action="store_true", help="启动后打开浏览器")

    subparsers.add_parser("mcp", help="启动 MCP stdio 服务")
    subparsers.add_parser("status", help="查看索引统计")
    subparsers.add_parser("doctor", help="检查本机环境")
    learning_parser = subparsers.add_parser("learning-pack", help="导出指定文档的可追溯离线学习包")
    learning_parser.add_argument("document_id", help="已索引文档 ID")

    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command == "init":
        write_default_config(config["_config_path"])
        created = initialize_library(config)
        connection = connect(database_path(config))
        initialize(connection)
        connection.close()
        _print({"config": config["_config_path"], "library": str(library_path(config)), "created_directories": created})
    elif args.command == "ingest":
        embedding_option = None if args.embeddings == "auto" else args.embeddings == "on"
        _print(ingest_library(config, args.path, force=args.force, embeddings=embedding_option))
    elif args.command == "search":
        _print(search(config, args.query, args.top_k, _filters(args), semantic=not args.lexical_only))
    elif args.command == "ask":
        _print(answer_question(config, args.question, args.mode, args.top_k, _filters(args)))
    elif args.command == "serve":
        host = args.host or config["server"]["host"]
        port = args.port or int(config["server"]["port"])
        if args.open:
            webbrowser.open("http://%s:%d" % (host, port))
        run_web(config, host, port)
    elif args.command == "mcp":
        run_mcp(config)
    elif args.command == "status":
        connection = connect(database_path(config))
        initialize(connection)
        value = stats(connection)
        connection.close()
        value["ollama"] = health(config)
        value["chat"] = chat_status(config)
        _print(value)
    elif args.command == "doctor":
        try:
            import pypdf  # type: ignore  # noqa: F401
            pdf = {"ready": True}
        except ImportError:
            pdf = {"ready": False, "fix": "运行 ./setup.command 安装 pypdf"}
        connection = connect(database_path(config))
        initialize(connection)
        fts = connection.execute("SELECT sqlite_version()").fetchone()[0]
        connection.close()
        _print({
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "sqlite": fts,
            "library": str(library_path(config)),
            "database": str(database_path(config)),
            "pdf_parser": pdf,
            "ollama": health(config),
            "chat": chat_status(config),
        })
    elif args.command == "learning-pack":
        _print(export_learning_pack(config, args.document_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
