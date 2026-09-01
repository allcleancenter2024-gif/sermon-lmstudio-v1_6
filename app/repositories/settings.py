"""SQLite-backed application settings without a dependency on app.core."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
import sqlite3
from pathlib import Path

from app.paths import DATA_DIR


DB_PATH = DATA_DIR / "bible.db"


@contextmanager
def _connect(*args, **kwargs):
    con = sqlite3.connect(*args, **kwargs)
    try:
        with con:
            yield con
    finally:
        con.close()


def ensure_settings_table(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS app_settings (
                   key TEXT PRIMARY KEY,
                   value_json TEXT NOT NULL,
                   updated_at TEXT NOT NULL
               )"""
        )


def get_json(key: str, db_path: Path = DB_PATH):
    ensure_settings_table(db_path)
    with _connect(db_path) as con:
        row = con.execute("SELECT value_json FROM app_settings WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return None


def set_json(key: str, value, db_path: Path = DB_PATH) -> None:
    ensure_settings_table(db_path)
    now = datetime.now().isoformat(timespec="seconds")
    with _connect(db_path) as con:
        con.execute(
            """INSERT INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
            (key, json.dumps(value), now),
        )


def get_reading_cpm(db_path: Path = DB_PATH) -> int:
    value = get_json("reading_cpm", db_path)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 330
    return min(max(value, 180), 600)


def set_reading_cpm(chars_per_minute: int, db_path: Path = DB_PATH) -> int:
    value = int(chars_per_minute)
    if not 180 <= value <= 600:
        raise ValueError("낭독속도는 공백 제외 180~600자/분 범위로 설정하세요.")
    set_json("reading_cpm", value, db_path)
    return value


def calibrate_reading_cpm(text: str, seconds: float, db_path: Path = DB_PATH) -> int:
    visible = len("".join(str(text).split()))
    if visible < 80 or seconds < 15:
        raise ValueError("보정용 본문은 공백 제외 80자 이상, 낭독시간은 15초 이상이어야 합니다.")
    measured = round(visible / (seconds / 60.0))
    return set_reading_cpm(min(max(measured, 180), 600), db_path)
