import pytest

from app.rag.pgvector import (
    MODEL_DIMENSION,
    PgVectorConfigurationError,
    create_pgvector_repository,
    vector_literal,
)


def test_pgvector_vector_literal_rejects_wrong_dimension_and_nonfinite_values():
    with pytest.raises(PgVectorConfigurationError, match="차원"):
        vector_literal([0.0])
    with pytest.raises(PgVectorConfigurationError, match="유한"):
        vector_literal([float("nan")] + [0.0] * (MODEL_DIMENSION - 1))


def test_pgvector_vector_literal_is_deterministic():
    literal = vector_literal([0.25] * MODEL_DIMENSION)
    assert literal.startswith("[0.25,0.25")
    assert literal.endswith("]")


def test_pgvector_repository_builds_a_loopback_url_from_dedicated_production_fields():
    repository = create_pgvector_repository(environ={
        "POSTGRES_RAG_PROD_DB": "rag_db",
        "POSTGRES_RAG_PROD_USER": "rag user",
        "POSTGRES_RAG_PROD_PASSWORD": "safe:password",
        "POSTGRES_RAG_PROD_PORT": "15434",
    })
    assert repository.adapter.database_url == "postgresql://rag%20user:safe%3Apassword@127.0.0.1:15434/rag_db"
