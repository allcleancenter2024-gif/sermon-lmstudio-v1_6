"""Approved-only, denomination-isolated doctrine RAG (SQLite V2 path)."""

from __future__ import annotations

from array import array
from contextlib import closing
from datetime import datetime, timezone
import math
from pathlib import Path
import sqlite3

from app.doctrine_workflow import fetch_indexable_doctrine_chunks, transition_document


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_approved_doctrine_index(client, model: str, db_path: Path, batch_size: int = 64) -> dict:
    chunks = fetch_indexable_doctrine_chunks(db_path)
    if not chunks:
        return {"indexed": 0, "index_version_id": None, "documents": 0, "message": "승인된 교리 청크가 없습니다."}
    vectors = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        vectors.extend(client.embeddings(model, [f"{x['section_path']} | {x['article_title']} | {x['content']}" for x in batch]))
    dimension = len(vectors[0])
    if not dimension or any(len(vector) != dimension for vector in vectors):
        raise ValueError("임베딩 차원이 일관되지 않아 교리 색인을 중단했습니다.")
    with closing(sqlite3.connect(db_path)) as con, con:
        version_id = con.execute("INSERT INTO doctrine_index_versions(model,dimension,distance_metric,status,created_at) VALUES(?,?,?,?,?)", (model, dimension, "cosine", "BUILDING", _now())).lastrowid
        rows = []
        for chunk, vector in zip(chunks, vectors):
            norm = math.sqrt(sum(float(x) * float(x) for x in vector))
            rows.append((chunk["id"], int(version_id), array("f", (float(x) for x in vector)).tobytes(), dimension, norm))
        con.executemany("""INSERT INTO doctrine_embeddings_v2(chunk_id,index_version_id,vector_blob,dimension,norm) VALUES(?,?,?,?,?) ON CONFLICT(chunk_id,index_version_id) DO UPDATE SET vector_blob=excluded.vector_blob,dimension=excluded.dimension,norm=excluded.norm""", rows)
        con.execute("UPDATE doctrine_index_versions SET status='READY',completed_at=? WHERE id=?", (_now(), int(version_id)))
        document_ids = sorted({int(x["document_id"]) for x in chunks})
    with closing(sqlite3.connect(db_path)) as con:
        approved_ids = {int(row[0]) for row in con.execute("SELECT id FROM doctrine_documents WHERE id IN (%s) AND review_status='APPROVED'" % ",".join("?" for _ in document_ids), document_ids)}
    for document_id in approved_ids:
        transition_document(document_id, "INDEXED", "system:indexer", "승인된 청크 색인 완료", db_path)
    return {"indexed": len(rows), "index_version_id": int(version_id), "documents": len(document_ids), "model": model}


def search_approved_doctrine(query: str, client, model: str, denomination_code: str, db_path: Path, limit: int = 6, include_common: bool = True) -> list[dict]:
    if not query.strip() or not denomination_code.strip():
        return []
    query_vector = client.embeddings(model, [query])[0]
    qnorm = math.sqrt(sum(float(x) * float(x) for x in query_vector))
    with closing(sqlite3.connect(db_path)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""SELECT c.id,c.document_id,c.section_path,c.article_number,c.article_title,c.content,c.scripture_refs,c.topic_tags,d.title AS document_title,d.edition,d.adoption_year,d.language,d.official_status,s.title AS source_title,s.source_url,n.code AS denomination_code,n.name_ko AS denomination_name,n.tradition AS tradition,e.vector_blob,e.dimension,e.norm,v.model,v.id AS index_version_id FROM doctrine_embeddings_v2 e JOIN doctrine_chunks_v2 c ON c.id=e.chunk_id JOIN doctrine_documents d ON d.id=c.document_id JOIN doctrine_sources s ON s.id=d.source_id JOIN denominations n ON n.id=s.denomination_id JOIN doctrine_index_versions v ON v.id=e.index_version_id WHERE v.model=? AND v.status='READY' AND d.review_status IN ('APPROVED','INDEXED') AND d.active=1 AND s.active=1 AND n.active=1 AND (n.code=? OR (?=1 AND n.code='COMMON'))""", (model, denomination_code.strip(), int(include_common))).fetchall()
    results = []
    for raw in rows:
        if int(raw["dimension"]) != len(query_vector):
            continue
        vector = array("f"); vector.frombytes(raw["vector_blob"])
        score = sum(float(a) * float(b) for a, b in zip(query_vector, vector)) / (qnorm * float(raw["norm"])) if qnorm and raw["norm"] else -1.0
        item = dict(raw)
        item.pop("vector_blob", None); item.pop("norm", None); item["score"] = score
        results.append(item)
    return sorted(results, key=lambda x: (-x["score"], x["id"]))[:max(1, min(limit, 50))]
