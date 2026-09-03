import sqlite3

from app.doctrine_backend import create_doctrine_backend
from app.doctrine_processing import read_document_processing_metadata, write_document_processing_metadata


def test_processing_metadata_uses_existing_sqlite_backend(tmp_path):
    db = tmp_path / "processing.sqlite3"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE doctrine_documents (id INTEGER PRIMARY KEY, metadata_json TEXT NOT NULL DEFAULT '{}')")
        con.execute("INSERT INTO doctrine_documents(id) VALUES (1)")
    write_document_processing_metadata(1, {"quality": {"passed": True}}, db)
    assert read_document_processing_metadata(1, db) == {"quality": {"passed": True}}
