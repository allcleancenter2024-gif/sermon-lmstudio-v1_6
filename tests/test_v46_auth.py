from pathlib import Path

from app.auth import create_session, create_user, revoke_session, session_user, user_count, verify_password


def test_local_auth_hashes_password_and_sessions_expire_on_revoke(tmp_path: Path):
    db = tmp_path / "auth.sqlite3"
    assert user_count(db) == 0
    assert create_user(db, "Pastor", "strong-password-123")
    assert user_count(db) == 1
    assert verify_password(db, "pastor", "strong-password-123")
    assert not verify_password(db, "pastor", "wrong-password")
    token = create_session("pastor")
    assert session_user(token) == "pastor"
    revoke_session(token)
    assert session_user(token) is None


def test_duplicate_user_and_weak_password_are_rejected(tmp_path: Path):
    db = tmp_path / "auth.sqlite3"
    try:
        create_user(db, "ab", "short")
        assert False
    except ValueError:
        pass
    assert create_user(db, "admin", "strong-password-123")
    assert not create_user(db, "ADMIN", "another-password-456")
