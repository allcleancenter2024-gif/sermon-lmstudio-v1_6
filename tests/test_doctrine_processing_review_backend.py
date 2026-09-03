import sqlite3

from app.doctrine_processing import read_document_for_processing, write_document_review_state


def test_processing_document_and_review_helpers_keep_sqlite_contract(tmp_path):
    db = tmp_path / "review.sqlite3"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE doctrine_documents (id INTEGER PRIMARY KEY, object_storage_key TEXT, mime_type TEXT, review_status TEXT, active INTEGER, metadata_json TEXT DEFAULT '{}')")
        con.execute("INSERT INTO doctrine_documents VALUES (1, 'x.txt', 'text/plain', 'DISCOVERED', 0, '{}')")
    assert read_document_for_processing(1, db)["review_status"] == "DISCOVERED"
    write_document_review_state(1, "NEEDS_REVIEW", False, db)
    assert read_document_for_processing(1, db)["review_status"] == "NEEDS_REVIEW"
