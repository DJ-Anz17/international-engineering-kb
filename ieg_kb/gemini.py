from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Sequence


class GeminiError(RuntimeError):
    pass


def _api_key() -> str:
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""


def status(config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "provider": "gemini",
        "enabled": bool(config.get("gemini", {}).get("enabled", False)),
        "configured": bool(_api_key()),
        "model": config.get("gemini", {}).get("model", "gemini-3.6-flash"),
        "models": list(config.get("gemini", {}).get("models", [])),
        "label": "Gemini（Google）",
        "cloud": True,
    }


def chat(config: Dict[str, Any], messages: Sequence[Dict[str, str]], temperature: float = 0.1) -> str:
    if not config.get("privacy", {}).get("allow_cloud_chat", False):
        raise GeminiError("隐私设置尚未允许把检索证据发送给 Gemini API。")
    if not config.get("gemini", {}).get("enabled", False):
        raise GeminiError("Gemini 已在配置中禁用。")
    key = _api_key()
    if not key:
        raise GeminiError("尚未配置 Gemini API Key；请双击 configure-gemini.command。")

    system_parts = [item["content"] for item in messages if item.get("role") == "system"]
    contents = []
    for item in messages:
        role = item.get("role")
        if role == "system":
            continue
        contents.append({
            "role": "model" if role == "assistant" else "user",
            "parts": [{"text": item.get("content", "")}],
        })
    payload: Dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"temperature": temperature},
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}

    gemini = config["gemini"]
    base_url = str(gemini.get("base_url", "https://generativelanguage.googleapis.com/v1beta")).rstrip("/")
    model = str(gemini.get("model", "gemini-3.6-flash"))
    endpoint = "%s/models/%s:generateContent" % (base_url, urllib.parse.quote(model, safe=""))
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=int(gemini.get("timeout_seconds", 180))) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            details = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", str(exc))
        except (json.JSONDecodeError, UnicodeDecodeError):
            details = str(exc)
        raise GeminiError("Gemini API 请求失败：%s" % details) from exc
    except (urllib.error.URLError, socket.timeout, json.JSONDecodeError) as exc:
        raise GeminiError("无法访问 Gemini API：%s" % exc) from exc

    candidates = value.get("candidates") or []
    if not candidates:
        block_reason = value.get("promptFeedback", {}).get("blockReason", "未返回候选答案")
        raise GeminiError("Gemini 未生成回答：%s" % block_reason)
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(str(part.get("text", "")) for part in parts).strip()
    if not text:
        raise GeminiError("Gemini 返回了空回答。")
    return text
