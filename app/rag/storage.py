"""Pure helpers for the serialized representation of RAG vectors."""

from __future__ import annotations

from array import array
import math


def pack_rag_vector(vector) -> tuple[bytes, int, float]:
    """Convert one embedding vector to SQLite storage bytes, dimension, and norm."""
    values = [float(x) for x in vector]
    packed = array("f", values).tobytes()
    norm = math.sqrt(sum(value * value for value in values))
    return packed, len(values), norm
