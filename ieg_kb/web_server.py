from __future__ import annotations

import cgi
import json
import mimetypes
import os
import re
import shutil
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, quote, unquote, urlparse

from .answer import answer_question
from .chat_provider import catalog as chat_catalog
from .chat_provider import status as chat_status
from .config import database_path, library_path, public_config, save_chat_selection
from .database import connect, initialize, stats
from .ingest import ingest_library
from .ollama import health
from .prompts import modes
from .search import get_document_chunks, search


class KnowledgeBaseHandler(BaseHTTPRequestHandler):
    server_version = "IEGKB/0.1"

    @property
    def config(self) -> Dict[str, Any]:
        return self.server.config  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def _json(self, value: Any, status: int = 200) -> None:
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 2 * 1024 * 1024:
            raise ValueError("请求过大")
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def _filters(self, body: Dict[str, Any]) -> Dict[str, str]:
        keys = ("category", "subcategory", "country", "project", "contract_form", "discipline", "document_type")
        return {key: str(body.get(key, "")) for key in keys if body.get(key)}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_static("index.html")
        elif parsed.path.startswith("/static/"):
            self._serve_static(parsed.path[len("/static/"):])
        elif parsed.path == "/api/status":
            connection = connect(database_path(self.config))
            initialize(connection)
            value = stats(connection)
            connection.close()
            value["ollama"] = health(self.config)
            value["chat"] = chat_status(self.config)
            value["modes"] = modes()
            self._json(value)
        elif parsed.path == "/api/config":
            self._json(public_config(self.config))
        elif parsed.path == "/api/document":
            query = parse_qs(parsed.query)
            self._json(get_document_chunks(
                self.config,
                query.get("id", [""])[0],
                int(query.get("offset", ["0"])[0]),
                int(query.get("limit", ["20"])[0]),
            ))
        elif parsed.path == "/api/file":
            self._serve_library_file(parse_qs(parsed.query).get("path", [""])[0])
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/api/search":
                body = self._body()
                self._json({"results": search(
                    self.config,
                    str(body.get("query", "")),
                    top_k=int(body.get("top_k", self.config["retrieval"]["top_k"])),
                    filters=self._filters(body),
                    semantic=bool(body.get("semantic", True)),
                )})
            elif parsed.path == "/api/ask":
                body = self._body()
                self._json(answer_question(
                    self.config,
                    str(body.get("query", "")),
                    mode=str(body.get("mode", "grounded_qa")),
                    top_k=int(body.get("top_k", self.config["retrieval"]["top_k"])),
                    filters=self._filters(body),
                ))
            elif parsed.path == "/api/reindex":
                body = self._body()
                self._json(ingest_library(self.config, force=bool(body.get("force", False))))
            elif parsed.path == "/api/chat-provider":
                body = self._body()
                provider = str(body.get("provider", "")).lower()
                model = str(body.get("model", "")).strip()
                available = {item["id"]: item for item in chat_catalog(self.config)}
                if provider not in available:
                    raise ValueError("不支持的 AI 提供商。")
                if not model or len(model) > 100 or any(char in model for char in "\\/\r\n"):
                    raise ValueError("模型名称无效。")
                save_chat_selection(self.config, provider, model)
                self._json({"chat": chat_status(self.config)})
            elif parsed.path == "/api/upload":
                self._upload()
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _serve_static(self, relative: str) -> None:
        root = Path(self.config["_root"]) / "web"
        target = (root / relative).resolve()
        if root.resolve() not in target.parents or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_library_file(self, relative: str) -> None:
        root = library_path(self.config).resolve()
        target = (root / unquote(relative)).resolve()
        if root not in target.parents or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", "inline; filename*=UTF-8''%s" % quote(target.name))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _upload(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > 200 * 1024 * 1024:
            raise ValueError("单次上传上限为 200 MB")
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")},
        )
        items = form["files"] if "files" in form else []
        if not isinstance(items, list):
            items = [items]
        inbox = library_path(self.config) / "00_待分类"
        inbox.mkdir(parents=True, exist_ok=True)
        allowed = {item.lower() for item in self.config["indexing"]["allowed_extensions"]}
        saved = []
        for item in items:
            if not getattr(item, "filename", ""):
                continue
            filename = Path(item.filename).name
            filename = re.sub(r"[\x00-\x1f/:]", "_", filename)
            if Path(filename).suffix.lower() not in allowed:
                continue
            target = inbox / filename
            if target.exists():
                target = inbox / (datetime.now().strftime("%Y%m%d_%H%M%S_") + filename)
            with target.open("wb") as handle:
                shutil.copyfileobj(item.file, handle)
            saved.append(target.name)
        report = ingest_library(self.config)
        self._json({"saved": saved, "ingest": report})


class KnowledgeBaseHTTPServer(ThreadingHTTPServer):
    def __init__(self, address: tuple, config: Dict[str, Any]):
        super().__init__(address, KnowledgeBaseHandler)
        self.config = config


def run(config: Dict[str, Any], host: str = "", port: int = 0) -> None:
    selected_host = host or str(config["server"]["host"])
    selected_port = port or int(config["server"]["port"])
    if config.get("privacy", {}).get("bind_local_only", True) and selected_host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("隐私设置只允许绑定本机地址；请修改 kb_config.json 后再开放局域网。")
    server = KnowledgeBaseHTTPServer((selected_host, selected_port), config)
    print("国际工程知识库：http://%s:%d" % (selected_host, selected_port))
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
