"""Explicit backend boundary for incremental doctrine repository migration."""

from __future__ import annotations

from dataclasses import dataclass

from app.db_adapter import create_database_adapter
from app.doctrine_repository_contract import DoctrineChunkRepository, DoctrineRepository


@dataclass(frozen=True)
class DoctrineBackend:
    name: str
    adapter: object
    repository: DoctrineRepository
    chunk_repository: DoctrineChunkRepository


def create_doctrine_backend(*, database_path=None, environ=None) -> DoctrineBackend:
    """Select doctrine persistence explicitly; existing remains the default."""
    adapter = create_database_adapter(database_path=database_path, environ=environ)
    return DoctrineBackend(name=adapter.backend, adapter=adapter, repository=DoctrineRepository(adapter),
                           chunk_repository=DoctrineChunkRepository(adapter))
