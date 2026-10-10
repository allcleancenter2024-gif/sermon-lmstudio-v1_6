from pathlib import Path

from app.auth import is_admin, verify_password
from create_initial_account import replace_initial_account


def test_replace_initial_account_makes_backup_and_new_admin(tmp_path: Path):
    db = tmp_path / "auth.sqlite3"
    from app.auth import create_user

    assert create_user(db, "old-user", "old-password-123")
    assert replace_initial_account(db, "new-admin", "new-password-456", "new-password-456", "REPLACE") == 0
    assert not verify_password(db, "old-user", "old-password-123")
    assert verify_password(db, "new-admin", "new-password-456")
    assert is_admin(db, "new-admin")
    assert len(list(tmp_path.glob("auth.sqlite3.pre-replace-*.bak"))) == 1


def test_replace_initial_account_requires_explicit_confirmation(tmp_path: Path):
    db = tmp_path / "auth.sqlite3"
    from app.auth import create_user

    assert create_user(db, "old-user", "old-password-123")
    assert replace_initial_account(db, "new-admin", "new-password-456", "new-password-456", "YES") == 2
    assert verify_password(db, "old-user", "old-password-123")
    assert not list(tmp_path.glob("auth.sqlite3.pre-replace-*.bak"))
