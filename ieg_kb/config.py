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
    },
    "ollama": {
        "enabled": True,
        "base_url": "http://127.0.0.1:11434",
        "chat_model": "qwen3:8b",
        "embedding_model": "bge-m3",
        "timeout_seconds": 180,
    },
    "server": {"host": "127.0.0.1", "port": 8765},
    "indexing": {
        "allowed_extensions": [
            ".txt", ".md", ".markdown", ".csv", ".tsv", ".json",
            ".html", ".htm", ".pdf", ".docx", ".xlsx", ".pptx",
            ".xml", ".yaml", ".yml", ".toml",
        ],
        "excluded_names": [".DS_Store", "Thumbs.db"],
        "embed_on_ingest": "auto",
    },
    "privacy": {
        "bind_local_only": True,
        "telemetry": False,
        "send_documents_to_cloud": False,
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


def write_default_config(path: Optional[str] = None, overwrite: bool = False) -> Path:
    target = Path(path).expanduser().resolve() if path else PROJECT_ROOT / "kb_config.json"
    if target.exists() and not overwrite:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
