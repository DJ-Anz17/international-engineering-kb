from __future__ import annotations

import json
import math
import socket
import struct
import urllib.error
import urllib.parse
import urllib.request
import time
from typing import Any, Dict, List, Optional, Sequence


class OllamaError(RuntimeError):
    pass


def _validate_url(config: Dict[str, Any]) -> str:
    base_url = str(config["ollama"]["base_url"]).rstrip("/")
    parsed = urllib.parse.urlparse(base_url)
    local_hosts = {"127.0.0.1", "localhost", "::1", "host.docker.internal"}
    if not config.get("privacy", {}).get("send_documents_to_cloud", False) and parsed.hostname not in local_hosts:
        raise OllamaError("隐私设置禁止把资料发送到非本机模型地址：%s" % base_url)
    return base_url


def _request(
    config: Dict[str, Any],
    endpoint: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    base_url = _validate_url(config)
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base_url + endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    effective_timeout = timeout or int(config["ollama"].get("timeout_seconds", 180))
    last_error: Optional[BaseException] = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=effective_timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 502, 503, 504} or attempt == 2:
                break
        except (urllib.error.URLError, socket.timeout, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == 2:
                break
        time.sleep(0.4 * (attempt + 1))
    raise OllamaError("无法访问本地 Ollama：%s" % last_error) from last_error


def health(config: Dict[str, Any]) -> Dict[str, Any]:
    if not config.get("ollama", {}).get("enabled", True):
        return {"available": False, "reason": "已在配置中禁用"}
    try:
        response = _request(config, "/api/tags", timeout=3)
        models = [item.get("name", "") for item in response.get("models", [])]
        chat_model = config["ollama"].get("chat_model", "")
        embedding_model = config["ollama"].get("embedding_model", "")
        return {
            "available": True,
            "models": models,
            "chat_model": chat_model,
            "embedding_model": embedding_model,
            "chat_model_ready": any(name == chat_model or name.startswith(chat_model + ":") for name in models),
            "embedding_model_ready": any(name == embedding_model or name.startswith(embedding_model + ":") for name in models),
        }
    except OllamaError as exc:
        return {"available": False, "reason": str(exc)}


def embed(config: Dict[str, Any], texts: Sequence[str]) -> List[List[float]]:
    if not texts:
        return []
    model = config["ollama"]["embedding_model"]
    try:
        response = _request(config, "/api/embed", {"model": model, "input": list(texts)})
        embeddings = response.get("embeddings")
        if isinstance(embeddings, list) and len(embeddings) == len(texts):
            return embeddings
    except OllamaError:
        if len(texts) != 1:
            result: List[List[float]] = []
            for text in texts:
                result.extend(embed(config, [text]))
            return result
    response = _request(config, "/api/embeddings", {"model": model, "prompt": texts[0]})
    embedding = response.get("embedding")
    if not isinstance(embedding, list):
        raise OllamaError("Ollama 未返回有效向量；请确认已执行 ollama pull %s" % model)
    return [embedding]


def chat(config: Dict[str, Any], messages: Sequence[Dict[str, str]], temperature: float = 0.1) -> str:
    model = config["ollama"]["chat_model"]
    response = _request(
        config,
        "/api/chat",
        {
            "model": model,
            "messages": list(messages),
            "stream": False,
            "options": {"temperature": temperature},
        },
    )
    content = response.get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise OllamaError("Ollama 未返回回答；请确认已执行 ollama pull %s" % model)
    return content.strip()


def pack_vector(values: Sequence[float]) -> bytes:
    return struct.pack("<%sf" % len(values), *values)


def unpack_vector(data: bytes, dimension: int) -> List[float]:
    return list(struct.unpack("<%sf" % dimension, data))


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)
