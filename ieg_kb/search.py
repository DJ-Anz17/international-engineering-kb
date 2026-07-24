from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .config import database_path
from .database import connect, initialize
from .ollama import OllamaError, cosine_similarity, embed, health, unpack_vector
from .tokenizer import fts_query


def _filter_sql(filters: Optional[Dict[str, str]], alias: str = "d") -> Tuple[str, List[str]]:
    clauses: List[str] = []
    params: List[str] = []
    mapping = {
        "category": "category",
        "subcategory": "subcategory",
        "country": "country",
        "project": "project",
        "contract_form": "contract_form",
        "discipline": "discipline",
        "document_type": "document_type",
    }
    for key, column in mapping.items():
        value = (filters or {}).get(key, "").strip()
        if value:
            clauses.append("%s.%s = ?" % (alias, column))
            params.append(value)
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def _row_result(row: Any) -> Dict[str, Any]:
    return {
        "chunk_id": int(row["chunk_id"]),
        "document_id": row["doc_id"],
        "title": row["title"],
        "path": row["rel_path"],
        "category": row["category"],
        "subcategory": row["subcategory"],
        "country": row["country"],
        "project": row["project"],
        "contract_form": row["contract_form"],
        "document_type": row["document_type"],
        "version": row["version"],
        "effective_date": row["effective_date"],
        "tags": json.loads(row["tags_json"] or "[]"),
        "locator": row["locator"],
        "heading": row["heading"],
        "content": row["content"],
    }


def search(
    config: Dict[str, Any],
    query: str,
    top_k: Optional[int] = None,
    filters: Optional[Dict[str, str]] = None,
    semantic: bool = True,
) -> List[Dict[str, Any]]:
    query = query.strip()
    if not query:
        return []
    limit = max(1, min(int(top_k or config["retrieval"]["top_k"]), 30))
    connection = connect(database_path(config))
    initialize(connection)
    filter_clause, filter_params = _filter_sql(filters)
    match = fts_query(query)
    lexical_rows = []
    if match:
        lexical_rows = connection.execute(
            """SELECT
                c.id AS chunk_id, c.doc_id, c.locator, c.heading, c.content,
                d.title, d.rel_path, d.category, d.subcategory, d.country, d.project,
                d.contract_form, d.document_type, d.version, d.effective_date, d.tags_json,
                bm25(chunks_fts, 0.0, 0.0, 1.0, 0.8, 0.5, 0.2, 0.2, 0.1) AS lexical_rank
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.chunk_id
            JOIN documents d ON d.id = c.doc_id
            WHERE chunks_fts MATCH ?""" + filter_clause + " ORDER BY lexical_rank LIMIT ?",
            [match] + filter_params + [max(50, limit * 8)],
        ).fetchall()

    by_id: Dict[int, Dict[str, Any]] = {}
    lexical_order: List[int] = []
    for row in lexical_rows:
        result = _row_result(row)
        chunk_id = result["chunk_id"]
        by_id[chunk_id] = result
        lexical_order.append(chunk_id)

    semantic_order: List[int] = []
    model_status = health(config) if semantic else {"embedding_model_ready": False}
    if semantic and model_status.get("embedding_model_ready", False):
        try:
            query_vector = embed(config, [query])[0]
            model = config["ollama"]["embedding_model"]
            vector_rows = connection.execute(
                """SELECT
                    c.id AS chunk_id, c.doc_id, c.locator, c.heading, c.content, c.vector, c.vector_dim,
                    d.title, d.rel_path, d.category, d.subcategory, d.country, d.project,
                    d.contract_form, d.document_type, d.version, d.effective_date, d.tags_json
                FROM chunks c JOIN documents d ON d.id = c.doc_id
                WHERE c.vector IS NOT NULL AND c.vector_model = ?""" + filter_clause,
                [model] + filter_params,
            ).fetchall()
            scored = []
            for row in vector_rows:
                vector = unpack_vector(row["vector"], int(row["vector_dim"]))
                scored.append((cosine_similarity(query_vector, vector), row))
            scored.sort(key=lambda item: item[0], reverse=True)
            for similarity, row in scored[:max(50, limit * 8)]:
                result = _row_result(row)
                result["semantic_similarity"] = round(similarity, 6)
                chunk_id = result["chunk_id"]
                if chunk_id not in by_id:
                    by_id[chunk_id] = result
                else:
                    by_id[chunk_id]["semantic_similarity"] = round(similarity, 6)
                semantic_order.append(chunk_id)
        except (OllamaError, ValueError):
            pass

    lexical_weight = float(config["retrieval"].get("lexical_weight", 0.65))
    semantic_weight = float(config["retrieval"].get("semantic_weight", 0.35))
    scores: Dict[int, float] = {chunk_id: 0.0 for chunk_id in by_id}
    for rank, chunk_id in enumerate(lexical_order, 1):
        scores[chunk_id] += lexical_weight / (60.0 + rank)
    for rank, chunk_id in enumerate(semantic_order, 1):
        scores[chunk_id] += semantic_weight / (60.0 + rank)
    ordered = sorted(by_id.values(), key=lambda item: scores[item["chunk_id"]], reverse=True)
    for index, item in enumerate(ordered[:limit], 1):
        item["rank"] = index
        item["score"] = round(scores[item["chunk_id"]], 8)
        item["retrieval"] = "hybrid" if item["chunk_id"] in lexical_order and item["chunk_id"] in semantic_order else (
            "semantic" if item["chunk_id"] in semantic_order else "lexical"
        )
    connection.close()
    return ordered[:limit]


def get_document_chunks(config: Dict[str, Any], document_id: str, offset: int = 0, limit: int = 20) -> Dict[str, Any]:
    connection = connect(database_path(config))
    initialize(connection)
    document = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not document:
        connection.close()
        raise KeyError("找不到文档：%s" % document_id)
    rows = connection.execute(
        "SELECT id, ordinal, locator, heading, content FROM chunks WHERE doc_id = ? ORDER BY ordinal LIMIT ? OFFSET ?",
        (document_id, min(max(limit, 1), 100), max(offset, 0)),
    ).fetchall()
    result = {
        "document": dict(document),
        "chunks": [dict(row) for row in rows],
        "offset": offset,
        "limit": limit,
    }
    result["document"]["tags"] = json.loads(result["document"].pop("tags_json", "[]"))
    result["document"]["warnings"] = json.loads(result["document"].pop("warnings_json", "[]"))
    connection.close()
    return result
