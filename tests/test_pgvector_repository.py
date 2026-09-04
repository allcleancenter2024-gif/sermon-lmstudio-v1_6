import pytest

from app.rag.pgvector import MODEL_DIMENSION, PgVectorConfigurationError, vector_literal


def test_pgvector_vector_literal_rejects_wrong_dimension_and_nonfinite_values():
    with pytest.raises(PgVectorConfigurationError, match="차원"):
        vector_literal([0.0])
    with pytest.raises(PgVectorConfigurationError, match="유한"):
        vector_literal([float("nan")] + [0.0] * (MODEL_DIMENSION - 1))


def test_pgvector_vector_literal_is_deterministic():
    literal = vector_literal([0.25] * MODEL_DIMENSION)
    assert literal.startswith("[0.25,0.25")
    assert literal.endswith("]")
