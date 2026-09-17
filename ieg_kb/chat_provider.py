from __future__ import annotations

from typing import Any, Dict, Sequence

from . import gemini
from . import ollama
from . import openai_compatible


LABELS = {
    "ollama": "Ollama（本地）",
    "gemini": "Gemini（Google）",
}


def provider_name(config: Dict[str, Any]) -> str:
    return str(config.get("chat", {}).get("provider", "ollama")).lower()


def status(config: Dict[str, Any]) -> Dict[str, Any]:
    provider = provider_name(config)
    if provider == "gemini":
        active = gemini.status(config)
    elif provider in openai_compatible.PROVIDERS:
        active = openai_compatible.status(config, provider)
    else:
        value = ollama.health(config)
        active = {
            "provider": "ollama",
            "label": LABELS["ollama"],
            "configured": bool(value.get("chat_model_ready", False)),
            "model": value.get("chat_model", config.get("ollama", {}).get("chat_model", "")),
            "models": value.get("models", []),
            "cloud": False,
            **value,
        }
    active["providers"] = catalog(config)
    return active


def catalog(config: Dict[str, Any]) -> list:
    ollama_value = ollama.health(config)
    embedding_model = str(config.get("ollama", {}).get("embedding_model", ""))
    local_models = [
        name for name in ollama_value.get("models", [])
        if name != embedding_model and not name.startswith(embedding_model + ":")
    ]
    selected_local = str(config.get("ollama", {}).get("chat_model", ""))
    if selected_local and selected_local not in local_models:
        local_models.insert(0, selected_local)
    values = [{
        "id": "ollama",
        "label": LABELS["ollama"],
        "configured": bool(ollama_value.get("chat_model_ready", False)),
        "model": config.get("ollama", {}).get("chat_model", ""),
        "models": local_models,
        "cloud": False,
    }]
    gemini_value = gemini.status(config)
    values.append({"id": "gemini", **{key: value for key, value in gemini_value.items() if key != "provider"}})
    for provider in openai_compatible.PROVIDERS:
        value = openai_compatible.status(config, provider)
        values.append({"id": provider, **{key: item for key, item in value.items() if key != "provider"}})
    return values


def chat(config: Dict[str, Any], messages: Sequence[Dict[str, str]], temperature: float = 0.1) -> str:
    provider = provider_name(config)
    if provider == "gemini":
        return gemini.chat(config, messages, temperature)
    if provider in openai_compatible.PROVIDERS:
        return openai_compatible.chat(config, provider, messages, temperature)
    if provider == "ollama":
        return ollama.chat(config, messages, temperature)
    raise ValueError("不支持的 AI 提供商：%s" % provider)
