import os
import sqlite3

import pytest

from app.config import DB_PATH, get_lmstudio_url
from app.db_adapter import create_database_adapter
from app.providers.lmstudio import LMStudioClient
from app.rag.semantic import cosine_similarity, restore_rag_vector


pytestmark = pytest.mark.integration


MODEL = "text-embedding-nomic-embed-text-v1.5"


def _sqlite_sample(limit=256):
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(
            """SELECT p.id, p.text, e.vector_json, e.vector_blob
               FROM rag_embeddings e JOIN passages p ON p.id=e.passage_id
               WHERE e.model=? ORDER BY p.id LIMIT ?""", (MODEL, limit)
        )]


def _sqlite_all():
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(
            """SELECT p.id, p.text, e.vector_json, e.vector_blob
               FROM rag_embeddings e JOIN passages p ON p.id=e.passage_id
               WHERE e.model=? ORDER BY p.id""", (MODEL,)
        )]


def _vector_literal(values):
    return "[" + ",".join(format(float(value), ".9g") for value in values) + "]"


def test_real_embedding_search_matches_sqlite_on_isolated_sample():
    if os.environ.get("RUN_PGVECTOR_SEARCH_COMPARISON") != "1":
        pytest.skip("명시적 pgvector 검색 비교 플래그가 없어 건너뜁니다.")

    url = os.environ.get("PGVECTOR_DATABASE_URL", "")
    if "sermon_pgvector_test" not in url or "sermon_db" in url.replace("sermon_pgvector_test", ""):
        pytest.fail("통합시험 대상은 sermon_pgvector_test로 제한됩니다.")

    rows = _sqlite_sample()
    assert len(rows) == 256
    query = rows[0]["text"]
    query_vector = LMStudioClient(base_url=get_lmstudio_url()).embeddings(MODEL, [query])[0]
    assert len(query_vector) == 768

    sqlite_ranked = sorted(
        ((row["id"], cosine_similarity(query_vector, restore_rag_vector(row["vector_blob"], row["vector_json"]))) for row in rows),
        key=lambda item: item[1], reverse=True,
    )[:10]

    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    with adapter.transaction() as connection:
        connection.execute("TRUNCATE rag_embedding_comparison")
        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO rag_embedding_comparison (passage_id, embedding) VALUES (%s, %s::vector)",
                [(row["id"], _vector_literal(restore_rag_vector(row["vector_blob"], row["vector_json"]))) for row in rows],
            )
        pg_ranked = connection.execute(
            """SELECT passage_id, 1 - (embedding <=> %s::vector) AS score
               FROM rag_embedding_comparison ORDER BY embedding <=> %s::vector LIMIT 10""",
            (_vector_literal(query_vector), _vector_literal(query_vector)),
        ).fetchall()

    assert [row["passage_id"] for row in pg_ranked] == [item[0] for item in sqlite_ranked]
    for pg_row, sqlite_row in zip(pg_ranked, sqlite_ranked):
        assert pg_row["score"] == pytest.approx(sqlite_row[1], abs=1e-5)


def test_multi_query_search_gate_preserves_sqlite_ranking():
    if os.environ.get("RUN_PGVECTOR_SEARCH_COMPARISON") != "1":
        pytest.skip("명시적 pgvector 검색 비교 플래그가 없어 건너뜁니다.")

    url = os.environ.get("PGVECTOR_DATABASE_URL", "")
    if "sermon_pgvector_test" not in url or "sermon_db" in url.replace("sermon_pgvector_test", ""):
        pytest.fail("통합시험 대상은 sermon_pgvector_test로 제한됩니다.")

    rows = _sqlite_sample()
    assert len(rows) == 256
    queries = [rows[index]["text"] for index in (0, 64, 128, 192)]
    query_vectors = LMStudioClient(base_url=get_lmstudio_url()).embeddings(MODEL, queries)
    assert all(len(vector) == 768 for vector in query_vectors)

    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    with adapter.transaction() as connection:
        connection.execute("TRUNCATE rag_embedding_comparison")
        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO rag_embedding_comparison (passage_id, embedding) VALUES (%s, %s::vector)",
                [(row["id"], _vector_literal(restore_rag_vector(row["vector_blob"], row["vector_json"]))) for row in rows],
            )
        for query_vector in query_vectors:
            sqlite_ranked = sorted(
                ((row["id"], cosine_similarity(query_vector, restore_rag_vector(row["vector_blob"], row["vector_json"]))) for row in rows),
                key=lambda item: item[1], reverse=True,
            )[:10]
            literal = _vector_literal(query_vector)
            pg_ranked = connection.execute(
                """SELECT passage_id, 1 - (embedding <=> %s::vector) AS score
                   FROM rag_embedding_comparison ORDER BY embedding <=> %s::vector LIMIT 10""",
                (literal, literal),
            ).fetchall()
            assert [row["passage_id"] for row in pg_ranked] == [item[0] for item in sqlite_ranked]
            for pg_row, sqlite_row in zip(pg_ranked, sqlite_ranked):
                assert pg_row["score"] == pytest.approx(sqlite_row[1], abs=1e-5)


def test_full_embedding_reindex_rehearsal_preserves_search_and_rollback():
    if os.environ.get("RUN_PGVECTOR_FULL_REHEARSAL") != "1":
        pytest.skip("명시적 전체 pgvector rehearsal 플래그가 없어 건너뜁니다.")

    url = os.environ.get("PGVECTOR_DATABASE_URL", "")
    if "sermon_pgvector_test" not in url or "sermon_db" in url.replace("sermon_pgvector_test", ""):
        pytest.fail("통합시험 대상은 sermon_pgvector_test로 제한됩니다.")

    rows = _sqlite_all()
    assert len(rows) == 31098
    queries = [rows[index]["text"] for index in (0, 7777, 15555, 23333)]
    query_vectors = LMStudioClient(base_url=get_lmstudio_url()).embeddings(MODEL, queries)
    assert all(len(vector) == 768 for vector in query_vectors)

    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    with adapter.transaction() as connection:
        connection.execute("TRUNCATE rag_embedding_comparison")
        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO rag_embedding_comparison (passage_id, embedding) VALUES (%s, %s::vector)",
                [(row["id"], _vector_literal(restore_rag_vector(row["vector_blob"], row["vector_json"]))) for row in rows],
            )
        count = connection.execute("SELECT COUNT(*) AS count FROM rag_embedding_comparison").fetchone()
        assert count["count"] == len(rows)
        for query_vector in query_vectors:
            sqlite_ranked = sorted(
                ((row["id"], cosine_similarity(query_vector, restore_rag_vector(row["vector_blob"], row["vector_json"]))) for row in rows),
                key=lambda item: item[1], reverse=True,
            )[:10]
            literal = _vector_literal(query_vector)
            pg_ranked = connection.execute(
                """SELECT passage_id, 1 - (embedding <=> %s::vector) AS score
                   FROM rag_embedding_comparison ORDER BY embedding <=> %s::vector LIMIT 10""",
                (literal, literal),
            ).fetchall()
            assert [row["passage_id"] for row in pg_ranked] == [item[0] for item in sqlite_ranked]
            for pg_row, sqlite_row in zip(pg_ranked, sqlite_ranked):
                assert pg_row["score"] == pytest.approx(sqlite_row[1], abs=1e-5)

    with pytest.raises(RuntimeError):
        with adapter.transaction() as connection:
            connection.execute("DELETE FROM rag_embedding_comparison")
            raise RuntimeError("full rehearsal rollback")

    with adapter.transaction() as connection:
        count = connection.execute("SELECT COUNT(*) AS count FROM rag_embedding_comparison").fetchone()
        assert count["count"] == len(rows)
        connection.execute("TRUNCATE rag_embedding_comparison")
