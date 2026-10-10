from pathlib import Path

from app.auth import is_admin, verify_password
from create_initial_account import create_initial_account


def test_initial_account_creates_admin_without_plaintext_password(tmp_path: Path):
    db = tmp_path / "auth.sqlite3"
    assert create_initial_account(db, "Pastor", "strong-password-123", "strong-password-123") == 0
    assert is_admin(db, "pastor")
    assert verify_password(db, "pastor", "strong-password-123")
    raw = db.read_bytes()
    assert b"strong-password-123" not in raw


def test_initial_account_never_overwrites_existing_user(tmp_path: Path):
    db = tmp_path / "auth.sqlite3"
    assert create_initial_account(db, "first", "strong-password-123", "strong-password-123") == 0
    assert create_initial_account(db, "second", "another-password-456", "another-password-456") == 3
    assert not verify_password(db, "second", "another-password-456")


def test_initial_account_rejects_mismatched_password(tmp_path: Path):
    db = tmp_path / "auth.sqlite3"
    assert create_initial_account(db, "first", "strong-password-123", "different-password-456") == 2
