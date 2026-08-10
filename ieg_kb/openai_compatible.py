from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, Sequence


PROVIDERS = {
    "qwen": {"label": "Qwen（阿里云百炼）", "key_env": "DASHSCOPE_API_KEY"},
    "kimi": {"label": "Kimi（月之暗面）", "key_env": "MOONSHOT_API_KEY"},
    "openai": {"label": "OpenAI", "key_env": "OPENAI_API_KEY"},
    "glm": {"label": "GLM（智谱）", "key_env": "ZAI_API_KEY"},
    "deepseek": {"label": "DeepSeek", "key_env": "DEEPSEEK_API_KEY"},
}


class CompatibleAPIError(RuntimeError):
    pass


def _settings(config: Dict[str, Any], provider: str) -> Dict[str, Any]:
    if provider not in PROVIDERS:
        raise CompatibleAPIError("不支持的云端模型提供商：%s" % provider)
    return config.get(provider, {})


def _api_key(config: Dict[str, Any], provider: str) -> str:
    settings = _settings(config, provider)
    env_name = str(settings.get("api_key_env") or PROVIDERS[provider]["key_env"])
    return os.environ.get(env_name, "")


def status(config: Dict[str, Any], provider: str) -> Dict[str, Any]:
    settings = _settings(config, provider)
    model = str(settings.get("model", ""))
    model_labels = dict(settings.get("model_labels", {}))
    model_options = dict(settings.get("model_options", {}))
    selected_options = model_options.get(model, {})
    return {
        "provider": provider,
        "label": PROVIDERS[provider]["label"],
        "enabled": bool(settings.get("enabled", False)),
        "configured": bool(_api_key(config, provider)),
        "model": model,
        "model_label": model_labels.get(model, model),
        "models": list(settings.get("models", [])),
        "model_labels": model_labels,
        "reasoning_effort": selected_options.get("reasoning_effort", ""),
        "cloud": True,
    }


def chat(
    config: Dict[str, Any],
    provider: str,
    messages: Sequence[Dict[str, str]],
    temperature: float = 0.1,
) -> str:
    settings = _settings(config, provider)
    label = PROVIDERS[provider]["label"]
    if not config.get("privacy", {}).get("allow_cloud_chat", False):
        raise CompatibleAPIError("隐私设置尚未允许把检索证据发送给云端 AI。")
    if not settings.get("enabled", False):
        raise CompatibleAPIError("%s 已在配置中禁用。" % label)
    key = _api_key(config, provider)
    if not key:
        raise CompatibleAPIError("尚未配置 %s API Key；请双击 configure-ai.command。" % label)

    base_url = str(settings.get("base_url", "")).rstrip("/")
    endpoint = base_url + "/chat/completions"
    model = str(settings.get("model", ""))
    model_options = dict(settings.get("model_options", {})).get(model, {})
    payload = {
        "model": model,
        "messages": list(messages),
        "stream": False,
    }
    reasoning_effort = str(model_options.get("reasoning_effort", ""))
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    else:
        payload["temperature"] = temperature
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=int(settings.get("timeout_seconds", 180))) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            error_value = json.loads(exc.read().decode("utf-8"))
            details = error_value.get("error", {}).get("message", str(exc))
        except (json.JSONDecodeError, UnicodeDecodeError):
            details = str(exc)
        raise CompatibleAPIError("%s API 请求失败：%s" % (label, details)) from exc
    except (urllib.error.URLError, socket.timeout, json.JSONDecodeError) as exc:
        raise CompatibleAPIError("无法访问 %s API：%s" % (label, exc)) from exc

    choices = value.get("choices") or []
    if not choices:
        raise CompatibleAPIError("%s 未返回候选答案。" % label)
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        content = "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    if not isinstance(content, str) or not content.strip():
        raise CompatibleAPIError("%s 返回了空回答。" % label)
    return content.strip()
