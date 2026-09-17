from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent


DEFAULT_CONFIG: Dict[str, Any] = {
    "library_dir": "library",
    "data_dir": "data",
    "database": "data/kb.sqlite3",
    "retrieval": {
        "top_k": 8,
        "chunk_chars": 1200,
        "chunk_overlap_chars": 180,
        "lexical_weight": 0.65,
        "semantic_weight": 0.35,
        "max_chunks_per_document": 3,
    },
    "ollama": {
        "enabled": True,
        "base_url": "http://127.0.0.1:11434",
        "chat_model": "qwen3:8b",
        "embedding_model": "bge-m3",
        "timeout_seconds": 180,
    },
    "chat": {
        "provider": "ollama",
    },
    "gemini": {
        "enabled": False,
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-3.6-flash",
        "models": ["gemini-3.6-flash", "gemini-3.1-pro-preview"],
        "timeout_seconds": 180,
    },
    "qwen": {
        "enabled": True,
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo"],
        "api_key_env": "DASHSCOPE_API_KEY",
        "timeout_seconds": 180,
    },
    "kimi": {
        "enabled": True,
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k2.6",
        "models": ["kimi-k2.6", "kimi-k3"],
        "api_key_env": "MOONSHOT_API_KEY",
        "timeout_seconds": 180,
    },
    "openai": {
        "enabled": True,
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-5.2",
        "models": ["gpt-5.6-luna", "gpt-5.2", "gpt-5-mini"],
        "model_labels": {
            "gpt-5.6-luna": "ChatGPT 5.6 Luna · Max",
        },
        "model_options": {
            "gpt-5.6-luna": {"reasoning_effort": "max"},
        },
        "api_key_env": "OPENAI_API_KEY",
        "timeout_seconds": 180,
    },
    "glm": {
        "enabled": True,
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-5.2",
        "models": ["glm-5.2", "glm-4.7", "glm-4.5-air"],
        "api_key_env": "ZAI_API_KEY",
        "timeout_seconds": 180,
    },
    "deepseek": {
        "enabled": True,
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
        "model_labels": {
            "deepseek-v4-flash": "DeepSeek V4 Flash · 深度思考",
            "deepseek-v4-pro": "DeepSeek V4 Pro · 深度思考",
        },
        "model_options": {
            "deepseek-v4-flash": {"reasoning_effort": "high"},
            "deepseek-v4-pro": {"reasoning_effort": "high"},
        },
        "api_key_env": "DEEPSEEK_API_KEY",
        "timeout_seconds": 180,
    },
    "server": {"host": "127.0.0.1", "port": 8765},
    "indexing": {
        "allowed_extensions": [
            ".txt", ".text", ".md", ".markdown", ".rst", ".adoc", ".asciidoc",
            ".csv", ".tsv", ".json", ".html", ".htm", ".xhtml",
            ".pdf", ".docx", ".xlsx", ".pptx", ".pptm",
            ".epub", ".rtf", ".mobi", ".azw", ".azw3",
            ".xml", ".yaml", ".yml", ".toml",
        ],
        "excluded_names": [".DS_Store", "Thumbs.db"],
        "embed_on_ingest": "auto",
    },
    "privacy": {
        "bind_local_only": True,
        "telemetry": False,
        "send_documents_to_cloud": False,
        "allow_cloud_chat": False,
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    raw_path = path or os.environ.get("IEG_KB_CONFIG") or str(PROJECT_ROOT / "kb_config.json")
    config_path = Path(raw_path).expanduser().resolve()
    user_config: Dict[str, Any] = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            user_config = json.load(handle)
    config = _deep_merge(DEFAULT_CONFIG, user_config)
    default_extensions = DEFAULT_CONFIG["indexing"]["allowed_extensions"]
    configured_extensions = config["indexing"].get("allowed_extensions", [])
    config["indexing"]["allowed_extensions"] = list(dict.fromkeys(
        str(value).lower() for value in [*configured_extensions, *default_extensions]
    ))
    config["_config_path"] = str(config_path)
    config["_root"] = str(config_path.parent)
    return config


def resolve_config_path(config: Dict[str, Any], value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path(config["_root"]) / path
    return path.resolve()


def database_path(config: Dict[str, Any]) -> Path:
    return resolve_config_path(config, config["database"])


def library_path(config: Dict[str, Any]) -> Path:
    return resolve_config_path(config, config["library_dir"])


def public_config(config: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in config.items() if not key.startswith("_")}


def save_chat_selection(config: Dict[str, Any], provider: str, model: str) -> None:
    """Persist only the active provider/model while preserving user settings."""
    config_path = Path(config["_config_path"])
    raw: Dict[str, Any] = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    raw.setdefault("chat", {})["provider"] = provider
    raw.setdefault(provider, {})["model"] = model
    config["chat"]["provider"] = provider
    config[provider]["model"] = model
    temporary = config_path.with_suffix(config_path.suffix + ".tmp")
    temporary.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(config_path)


def write_default_config(path: Optional[str] = None, overwrite: bool = False) -> Path:
    target = Path(path).expanduser().resolve() if path else PROJECT_ROOT / "kb_config.json"
    if target.exists() and not overwrite:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
