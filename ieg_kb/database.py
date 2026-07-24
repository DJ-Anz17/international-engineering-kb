from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    rel_path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    subcategory TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    project TEXT NOT NULL DEFAULT '',
    contract_form TEXT NOT NULL DEFAULT '',
    discipline TEXT NOT NULL DEFAULT '',
    document_type TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT '',
    effective_date TEXT NOT NULL DEFAULT '',
    confidentiality TEXT NOT NULL DEFAULT '内部',
    source_org TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    checksum TEXT NOT NULL,
    mtime REAL NOT NULL,
    indexed_at TEXT NOT NULL,
    parser TEXT NOT NULL DEFAULT '',
    warnings_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    locator TEXT NOT NULL DEFAULT '',
    heading TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    search_tokens TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    vector BLOB,
    vector_dim INTEGER,
    vector_model TEXT NOT NULL DEFAULT '',
    UNIQUE(doc_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
CREATE INDEX IF NOT EXISTS idx_documents_country ON documents(country);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    doc_id UNINDEXED,
    content,
    search_tokens,
    title,
    category,
    country,
    tags,
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    connection.commit()


def stats(connection: sqlite3.Connection) -> Dict[str, Any]:
    documents = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunks = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    embedded = connection.execute("SELECT COUNT(*) FROM chunks WHERE vector IS NOT NULL").fetchone()[0]
    warnings = connection.execute(
        "SELECT COUNT(*) FROM documents WHERE warnings_json <> '[]'"
    ).fetchone()[0]
    categories = [
        dict(row)
        for row in connection.execute(
            "SELECT category, COUNT(*) AS count FROM documents GROUP BY category ORDER BY category"
        ).fetchall()
    ]
    return {
        "documents": documents,
        "chunks": chunks,
        "embedded_chunks": embedded,
        "documents_with_warnings": warnings,
        "categories": categories,
    }
