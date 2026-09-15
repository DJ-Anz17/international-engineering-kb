from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from .answer import answer_question
from .config import database_path
from .database import connect, initialize, stats
from .prompts import modes
from .search import get_document_chunks, search


PROTOCOL_VERSION = "2025-06-18"


def _tool_definitions() -> list:
    filters = {
        "document_id": {"type": "string", "description": "只检索指定文档 ID"},
        "category": {"type": "string", "description": "如：合同与索赔、投标报价"},
        "country": {"type": "string", "description": "国别精确筛选"},
        "project": {"type": "string", "description": "项目名精确筛选"},
        "contract_form": {"type": "string", "description": "合同范本，如 FIDIC 2017 Red Book"},
    }
    return [
        {
            "name": "kb_search",
            "description": "检索本地国际工程知识库，返回可引用的原文片段。适用于投标、技术、工效、风险、合同、国别等问题。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "自然语言问题或关键词"},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 30, "default": 8},
                    **filters,
                },
                "required": ["query"],
            },
        },
        {
            "name": "kb_get_document",
            "description": "按文档 ID 分页读取已索引文档的原文块。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                },
                "required": ["document_id"],
            },
        },
        {
            "name": "kb_status",
            "description": "查看知识库文档数、片段数、分类与索引状态。",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "kb_answer",
            "description": "调用配置的 AI 服务，以知识库检索结果为唯一证据生成带引用的国际工程分析。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "mode": {
                        "type": "string",
                        "enum": [item["id"] for item in modes()],
                        "default": "grounded_qa",
                    },
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 30, "default": 8},
                    **filters,
                },
                "required": ["question"],
            },
        },
    ]


def _filters(arguments: Dict[str, Any]) -> Dict[str, str]:
    keys = ("document_id", "category", "country", "project", "contract_form")
    return {key: str(arguments.get(key, "")) for key in keys if arguments.get(key)}


def _call_tool(config: Dict[str, Any], name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "kb_search":
        value = search(
            config,
            str(arguments.get("query", "")),
            top_k=int(arguments.get("top_k", 8)),
            filters=_filters(arguments),
        )
    elif name == "kb_get_document":
        value = get_document_chunks(
            config,
            str(arguments["document_id"]),
            offset=int(arguments.get("offset", 0)),
            limit=int(arguments.get("limit", 20)),
        )
    elif name == "kb_status":
        connection = connect(database_path(config))
        initialize(connection)
        value = stats(connection)
        connection.close()
    elif name == "kb_answer":
        value = answer_question(
            config,
            str(arguments.get("question", "")),
            mode=str(arguments.get("mode", "grounded_qa")),
            top_k=int(arguments.get("top_k", 8)),
            filters=_filters(arguments),
        )
    else:
        raise KeyError("未知工具：%s" % name)
    return {
        "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, indent=2)}],
        "structuredContent": value,
        "isError": False,
    }


def _response(request_id: Any, result: Optional[Dict[str, Any]] = None, error: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    value: Dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        value["error"] = error
    else:
        value["result"] = result or {}
    return value


def run(config: Dict[str, Any]) -> None:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            request = json.loads(raw)
            method = request.get("method")
            request_id = request.get("id")
            if method == "initialize":
                result = {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "international-engineering-kb", "version": "0.2.0"},
                }
            elif method == "tools/list":
                result = {"tools": _tool_definitions()}
            elif method == "tools/call":
                params = request.get("params", {})
                result = _call_tool(config, str(params.get("name", "")), params.get("arguments", {}) or {})
            elif method == "ping":
                result = {}
            elif method and method.startswith("notifications/"):
                continue
            else:
                raise KeyError("不支持的方法：%s" % method)
            if request_id is not None:
                sys.stdout.write(json.dumps(_response(request_id, result=result), ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            request_id = request.get("id") if isinstance(locals().get("request"), dict) else None
            if request_id is not None:
                error = {"code": -32000, "message": str(exc)}
                sys.stdout.write(json.dumps(_response(request_id, error=error), ensure_ascii=False) + "\n")
                sys.stdout.flush()
