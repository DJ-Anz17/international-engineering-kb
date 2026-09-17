from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .config import database_path, library_path
from .database import connect, initialize
from .material_security import scan_material
from .ollama import OllamaError, embed, health, pack_vector
from .parsers import ParsedUnit, parse_file
from .tokenizer import search_token_text


METADATA_FIELDS = {
    "title", "category", "subcategory", "country", "project", "contract_form",
    "discipline", "document_type", "language", "version", "effective_date",
    "confidentiality", "source_org", "tags",
}


def _clean_folder_label(value: str) -> str:
    return re.sub(r"^\d+[_\- ]*", "", value).replace("_", " ").strip()


def _title_from_path(path: Path) -> str:
    return re.sub(r"[_\-]+", " ", path.stem).strip()


def _sidecar_paths(path: Path) -> List[Path]:
    return [Path(str(path) + ".meta.json"), path.with_suffix(".meta.json")]


def _read_metadata(path: Path, rel_path: Path) -> Tuple[Dict[str, Any], List[str]]:
    parts = rel_path.parts
    metadata: Dict[str, Any] = {
        "title": _title_from_path(path),
        "category": _clean_folder_label(parts[0]) if len(parts) > 1 else "未分类",
        "subcategory": _clean_folder_label(parts[1]) if len(parts) > 2 else "",
        "country": "",
        "project": "",
        "contract_form": "",
        "discipline": "",
        "document_type": path.suffix.lower().lstrip("."),
        "language": "",
        "version": "",
        "effective_date": "",
        "confidentiality": "内部",
        "source_org": "",
        "tags": [],
    }
    warnings: List[str] = []
    sidecar = next((candidate for candidate in _sidecar_paths(path) if candidate.exists()), None)
    if sidecar:
        try:
            value = json.loads(sidecar.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("顶层必须是 JSON 对象")
            for key in METADATA_FIELDS:
                if key in value:
                    metadata[key] = value[key]
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            warnings.append("元数据文件 %s 无效：%s" % (sidecar.name, exc))
    if not isinstance(metadata.get("tags"), list):
        metadata["tags"] = [str(metadata["tags"])]
    return metadata, warnings


def _source_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    for sidecar in _sidecar_paths(path):
        if sidecar.exists():
            digest.update(sidecar.read_bytes())
            break
    return digest.hexdigest()


def _document_id(rel_path: str) -> str:
    return hashlib.sha256(rel_path.encode("utf-8")).hexdigest()[:20]


def _security_warning(security: Dict[str, Any]) -> str:
    kinds = sorted({item["kind"] for item in security.get("findings", [])})
    return "材料安全扫描需要人工复核：%s" % "、".join(kinds)


def _split_long_text(text: str, maximum: int, overlap: int) -> Iterable[str]:
    start = 0
    length = len(text)
    while start < length:
        end = min(length, start + maximum)
        if end < length:
            boundary = max(text.rfind("\n", start + maximum // 2, end), text.rfind("。", start + maximum // 2, end))
            if boundary > start:
                end = boundary + 1
        value = text[start:end].strip()
        if value:
            yield value
        if end >= length:
            break
        start = max(start + 1, end - overlap)


def _chunk_units(units: Sequence[ParsedUnit], maximum: int, overlap: int) -> List[Dict[str, str]]:
    chunks: List[Dict[str, str]] = []
    for unit in units:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", unit.text) if part.strip()]
        buffer = ""
        for paragraph in paragraphs:
            if len(paragraph) > maximum:
                if buffer:
                    chunks.append({"locator": unit.locator, "heading": _heading(buffer), "content": buffer})
                    buffer = ""
                for part in _split_long_text(paragraph, maximum, overlap):
                    chunks.append({"locator": unit.locator, "heading": _heading(part), "content": part})
                continue
            candidate = paragraph if not buffer else buffer + "\n\n" + paragraph
            if len(candidate) <= maximum:
                buffer = candidate
            else:
                chunks.append({"locator": unit.locator, "heading": _heading(buffer), "content": buffer})
                tail = buffer[-overlap:].strip() if overlap else ""
                buffer = (tail + "\n\n" + paragraph).strip() if tail else paragraph
        if buffer:
            chunks.append({"locator": unit.locator, "heading": _heading(buffer), "content": buffer})
    return chunks


def _heading(text: str) -> str:
    first = text.splitlines()[0].strip().lstrip("#").strip() if text else ""
    return first if 0 < len(first) <= 100 else ""


def _iter_files(root: Path, config: Dict[str, Any], selected: Optional[Path] = None) -> Iterable[Path]:
    allowed = {item.lower() for item in config["indexing"]["allowed_extensions"]}
    excluded = set(config["indexing"].get("excluded_names", []))
    scope = selected or root
    candidates = [scope] if scope.is_file() else scope.rglob("*")
    for path in candidates:
        if not path.is_file() or path.name in excluded or path.name.startswith("."):
            continue
        if path.name.endswith(".meta.json"):
            continue
        if path.suffix.lower() in allowed:
            yield path


def ingest_library(
    config: Dict[str, Any],
    selected_path: Optional[str] = None,
    force: bool = False,
    embeddings: Optional[bool] = None,
) -> Dict[str, Any]:
    root = library_path(config)
    root.mkdir(parents=True, exist_ok=True)
    selected = Path(selected_path).expanduser().resolve() if selected_path else None
    if selected and root not in selected.parents and selected != root:
        raise ValueError("只允许索引知识库目录内的文件：%s" % root)
    connection = connect(database_path(config))
    initialize(connection)

    embed_setting = config["indexing"].get("embed_on_ingest", "auto")
    model_status = health(config)
    if embeddings is None:
        should_embed = embed_setting is True or (embed_setting == "auto" and model_status.get("embedding_model_ready", False))
    else:
        should_embed = embeddings

    report: Dict[str, Any] = {
        "indexed": 0,
        "skipped": 0,
        "removed": 0,
        "warnings": [],
        "embedding_enabled": should_embed,
        "embedding_model": config["ollama"].get("embedding_model", ""),
        "embedding_failures": 0,
        "pending_embeddings": 0,
        "security_review_required": 0,
        "files": [],
    }
    seen_paths = set()
    for path in sorted(_iter_files(root, config, selected), key=lambda item: str(item).lower()):
        rel_path = path.relative_to(root).as_posix()
        seen_paths.add(rel_path)
        checksum = _source_checksum(path)
        existing = connection.execute(
            "SELECT id, checksum, warnings_json, security_json FROM documents WHERE rel_path = ?",
            (rel_path,),
        ).fetchone()
        if existing and existing["checksum"] == checksum and not force:
            if not existing["security_json"] or existing["security_json"] == "{}":
                stored_text = "\n\n".join(
                    row[0] for row in connection.execute(
                        "SELECT content FROM chunks WHERE doc_id = ? ORDER BY ordinal", (existing["id"],)
                    ).fetchall()
                )
                security = scan_material(path, stored_text)
                stored_warnings = json.loads(existing["warnings_json"] or "[]")
                if security["status"] == "review-required":
                    report["security_review_required"] += 1
                    warning = _security_warning(security)
                    if warning not in stored_warnings:
                        stored_warnings.append(warning)
                with connection:
                    connection.execute(
                        "UPDATE documents SET security_json = ?, warnings_json = ? WHERE id = ?",
                        (json.dumps(security, ensure_ascii=False), json.dumps(stored_warnings, ensure_ascii=False), existing["id"]),
                    )
            missing_vectors = 0
            if should_embed:
                missing_vectors = connection.execute(
                    "SELECT COUNT(*) FROM chunks WHERE doc_id = ? AND (vector IS NULL OR vector_model <> ?)",
                    (existing["id"], config["ollama"]["embedding_model"]),
                ).fetchone()[0]
            if not missing_vectors:
                report["skipped"] += 1
                continue

        metadata, warnings = _read_metadata(path, Path(rel_path))
        try:
            parsed = parse_file(path)
            warnings.extend(parsed.warnings)
            chunks = _chunk_units(
                parsed.units,
                int(config["retrieval"]["chunk_chars"]),
                int(config["retrieval"]["chunk_overlap_chars"]),
            )
        except Exception as exc:  # a malformed office file should not stop the whole library
            parsed = None
            chunks = []
            warnings.append("解析失败：%s" % exc)

        extracted_text = "\n\n".join(item["content"] for item in chunks)
        security = scan_material(path, extracted_text)
        if security["status"] == "review-required":
            report["security_review_required"] += 1
            warnings.append(_security_warning(security))

        vectors: List[Optional[List[float]]] = [None] * len(chunks)
        if should_embed and chunks:
            try:
                batch_size = 16
                for start in range(0, len(chunks), batch_size):
                    batch = [item["content"] for item in chunks[start:start + batch_size]]
                    embedded = embed(config, batch)
                    for offset, vector in enumerate(embedded):
                        vectors[start + offset] = vector
            except OllamaError as exc:
                warnings.append("向量化失败，已保留全文索引：%s" % exc)
                report["embedding_failures"] += 1

        document_id = _document_id(rel_path)
        now = datetime.now(timezone.utc).isoformat()
        parser_name = parsed.parser if parsed else "error"
        tags_json = json.dumps(metadata["tags"], ensure_ascii=False)
        with connection:
            previous = connection.execute("SELECT id FROM documents WHERE rel_path = ?", (rel_path,)).fetchone()
            if previous:
                connection.execute("DELETE FROM chunks_fts WHERE doc_id = ?", (previous["id"],))
                connection.execute("DELETE FROM chunks WHERE doc_id = ?", (previous["id"],))
                connection.execute("DELETE FROM documents WHERE id = ?", (previous["id"],))
            connection.execute(
                """INSERT INTO documents (
                    id, rel_path, title, category, subcategory, country, project, contract_form,
                    discipline, document_type, language, version, effective_date, confidentiality,
                    source_org, tags_json, checksum, mtime, indexed_at, parser, warnings_json,
                    security_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    document_id, rel_path, str(metadata["title"]), str(metadata["category"]),
                    str(metadata["subcategory"]), str(metadata["country"]), str(metadata["project"]),
                    str(metadata["contract_form"]), str(metadata["discipline"]),
                    str(metadata["document_type"]), str(metadata["language"]), str(metadata["version"]),
                    str(metadata["effective_date"]), str(metadata["confidentiality"]),
                    str(metadata["source_org"]), tags_json, checksum, path.stat().st_mtime, now,
                    parser_name, json.dumps(warnings, ensure_ascii=False),
                    json.dumps(security, ensure_ascii=False),
                ),
            )
            for ordinal, (chunk, vector) in enumerate(zip(chunks, vectors)):
                content_hash = hashlib.sha256(chunk["content"].encode("utf-8")).hexdigest()
                vector_blob = pack_vector(vector) if vector else None
                vector_dim = len(vector) if vector else None
                cursor = connection.execute(
                    """INSERT INTO chunks (
                        doc_id, ordinal, locator, heading, content, search_tokens, content_hash,
                        vector, vector_dim, vector_model
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        document_id, ordinal, chunk["locator"], chunk["heading"], chunk["content"],
                        search_token_text(chunk["content"]), content_hash, vector_blob, vector_dim,
                        config["ollama"]["embedding_model"] if vector else "",
                    ),
                )
                connection.execute(
                    "INSERT INTO chunks_fts (chunk_id, doc_id, content, search_tokens, title, category, country, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        cursor.lastrowid, document_id, chunk["content"], search_token_text(chunk["content"]),
                        metadata["title"], metadata["category"], metadata["country"], " ".join(metadata["tags"]),
                    ),
                )
        report["indexed"] += 1
        report["files"].append({
            "path": rel_path,
            "chunks": len(chunks),
            "warnings": warnings,
            "security": security,
        })
        report["warnings"].extend("%s：%s" % (rel_path, warning) for warning in warnings)

    if selected is None:
        stale = connection.execute("SELECT id, rel_path FROM documents").fetchall()
        for row in stale:
            if row["rel_path"] not in seen_paths:
                with connection:
                    connection.execute("DELETE FROM chunks_fts WHERE doc_id = ?", (row["id"],))
                    connection.execute("DELETE FROM documents WHERE id = ?", (row["id"],))
                report["removed"] += 1
    report["pending_embeddings"] = connection.execute("SELECT COUNT(*) FROM chunks WHERE vector IS NULL").fetchone()[0]
    connection.close()
    return report
