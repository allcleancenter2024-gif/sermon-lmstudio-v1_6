from array import array

import pytest

from app.rag.semantic import semantic_search


class _Client:
    def embeddings(self, _model, _texts):
        return [[1.0, 0.0]]


def _sqlite_rows():
    return [{"id": 1, "translation": "TEST", "language": "ko", "reference": "테스트 1:1",
             "text": "본문", "license_note": "", "vector_blob": array("f", [1.0, 0.0]).tobytes(),
             "vector_json": "[]", "norm": 1.0}]


def test_sqlite_remains_default_route(monkeypatch):
    monkeypatch.delenv("RAG_BACKEND", raising=False)
    monkeypatch.setattr("app.rag.semantic.fetch_rag_vector_rows", lambda _model, *_args: _sqlite_rows())
    result = semantic_search("본문", _Client(), "test-model", limit=1)
    assert result[0]["id"] == 1


def test_verified_pgvector_route_uses_repository(monkeypatch):
    class _Repository:
        def search(self, vector, model, limit):
            assert vector == [1.0, 0.0]
            assert model == "test-model"
            assert limit == 1
            return [{"id": 2, "semantic_score": 0.9}]

    monkeypatch.setenv("RAG_BACKEND", "postgres_pgvector")
    monkeypatch.setenv("RAG_PGVECTOR_CAPABILITY_VERIFIED", "true")
    monkeypatch.setattr("app.rag.semantic.create_pgvector_repository", lambda: _Repository())
    assert semantic_search("본문", _Client(), "test-model", limit=1)[0]["id"] == 2


def test_pgvector_failure_falls_back_to_sqlite(monkeypatch):
    class _UnavailableRepository:
        def search(self, *_args):
            raise RuntimeError("pgvector unavailable")

    monkeypatch.setenv("RAG_BACKEND", "postgres_pgvector")
    monkeypatch.setenv("RAG_PGVECTOR_CAPABILITY_VERIFIED", "true")
    monkeypatch.setenv("RAG_PGVECTOR_FALLBACK_TO_SQLITE", "true")
    monkeypatch.setattr("app.rag.semantic.create_pgvector_repository", lambda: _UnavailableRepository())
    monkeypatch.setattr("app.rag.semantic.fetch_rag_vector_rows", lambda _model, *_args: _sqlite_rows())
    assert semantic_search("본문", _Client(), "test-model", limit=1)[0]["id"] == 1


def test_pgvector_failure_is_visible_when_fallback_is_disabled(monkeypatch):
    class _UnavailableRepository:
        def search(self, *_args):
            raise RuntimeError("pgvector unavailable")

    monkeypatch.setenv("RAG_BACKEND", "postgres_pgvector")
    monkeypatch.setenv("RAG_PGVECTOR_CAPABILITY_VERIFIED", "true")
    monkeypatch.setenv("RAG_PGVECTOR_FALLBACK_TO_SQLITE", "false")
    monkeypatch.setattr("app.rag.semantic.create_pgvector_repository", lambda: _UnavailableRepository())
    with pytest.raises(RuntimeError, match="unavailable"):
        semantic_search("본문", _Client(), "test-model", limit=1)
