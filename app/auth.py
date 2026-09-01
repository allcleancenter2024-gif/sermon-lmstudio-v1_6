"""Small local authentication boundary for the desktop/web application.

Accounts live in a separate SQLite file so the sermon database schema and data
remain untouched. Passwords are PBKDF2 hashes; sessions are short-lived
process-local bearer tokens stored only in memory.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path
from time import time

ITERATIONS = 240_000
SESSION_TTL = 12 * 60 * 60
_sessions: dict[str, tuple[str, float]] = {}


def _db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, created_at REAL NOT NULL)")
    con.commit()
    return con


def user_count(path: Path) -> int:
    with _db(path) as con:
        return int(con.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def create_user(path: Path, username: str, password: str) -> bool:
    username = username.strip().lower()
    if not (3 <= len(username) <= 80 and 10 <= len(password) <= 256):
        raise ValueError("사용자명은 3~80자, 비밀번호는 10자 이상이어야 합니다.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    encoded = f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"
    try:
        with _db(path) as con:
            con.execute("INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)", (username, encoded, time()))
        return True
    except sqlite3.IntegrityError:
        return False


def verify_password(path: Path, username: str, password: str) -> bool:
    with _db(path) as con:
        row = con.execute("SELECT password_hash FROM users WHERE username=?", (username.strip().lower(),)).fetchone()
    if not row:
        return False
    try:
        _, rounds, salt_hex, digest_hex = row[0].split("$", 3)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)).hex()
        return hmac.compare_digest(actual, digest_hex)
    except (ValueError, TypeError):
        return False


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = (username.strip().lower(), time() + SESSION_TTL)
    return token


def session_user(token: str | None) -> str | None:
    if not token:
        return None
    value = _sessions.get(token)
    if not value:
        return None
    username, expires = value
    if expires <= time():
        _sessions.pop(token, None)
        return None
    return username


def revoke_session(token: str | None) -> None:
    if token:
        _sessions.pop(token, None)
