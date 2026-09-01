from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


BACKUP_FORMAT = "sermon-lmstudio-backup-v1"
DB_ENTRY = "data/bible.db"
MANIFEST_ENTRY = "manifest.json"
MAX_BACKUP_BYTES = 512 * 1024 * 1024
REQUIRED_TABLES = {
    "passages",
    "rag_embeddings",
    "translation_licenses",
    "sermons",
    "sermon_versions",
    "app_settings",
}


class BackupError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_archive_names(archive: zipfile.ZipFile) -> None:
    infos = archive.infolist()
    if not infos or len(infos) > 8:
        raise BackupError("백업 파일의 항목 구성이 올바르지 않습니다.")
    total = 0
    for info in infos:
        name = info.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or name.startswith("/"):
            raise BackupError("안전하지 않은 백업 파일 경로가 포함되어 있습니다.")
        if info.flag_bits & 0x1:
            raise BackupError("암호화된 ZIP 백업은 복원할 수 없습니다.")
        total += info.file_size
        if total > MAX_BACKUP_BYTES:
            raise BackupError("백업 압축 해제 크기가 512MB 제한을 초과합니다.")
    names = {i.filename.replace("\\", "/") for i in infos if not i.is_dir()}
    if names != {MANIFEST_ENTRY, DB_ENTRY}:
        raise BackupError("이 프로그램이 만든 통합 백업 형식이 아닙니다.")


def _validate_sqlite(path: Path) -> dict:
    try:
        # sqlite3.Connection의 컨텍스트 관리자는 트랜잭션만 끝내며 연결은
        # 닫지 않는다. Windows에서는 열린 연결이 임시 DB 삭제를 막으므로
        # closing()으로 파일 핸들을 반드시 해제한다.
        with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as con:
            quick = str(con.execute("PRAGMA quick_check").fetchone()[0])
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            missing = sorted(REQUIRED_TABLES - tables)
            if quick.lower() != "ok":
                raise BackupError(f"SQLite 무결성 검사 실패: {quick}")
            if missing:
                raise BackupError("필수 DB 테이블이 없습니다: " + ", ".join(missing))
            return {
                "quick_check": quick,
                "passages": int(con.execute("SELECT COUNT(*) FROM passages").fetchone()[0]),
                "sermons": int(con.execute("SELECT COUNT(*) FROM sermons").fetchone()[0]),
            }
    except BackupError:
        raise
    except sqlite3.DatabaseError as exc:
        raise BackupError(f"유효한 설교 DB가 아닙니다: {exc}") from exc


def inspect_backup(path: Path) -> dict:
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_BACKUP_BYTES:
        raise BackupError("백업 파일이 없거나 512MB 제한을 초과합니다.")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            _safe_archive_names(archive)
            try:
                manifest = json.loads(archive.read(MANIFEST_ENTRY).decode("utf-8"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BackupError("백업 manifest.json을 읽을 수 없습니다.") from exc
            if manifest.get("format") != BACKUP_FORMAT:
                raise BackupError("지원하지 않는 백업 형식입니다.")
            expected = str(manifest.get("database", {}).get("sha256", ""))
            with tempfile.TemporaryDirectory(prefix="sermon-backup-check-") as tmp:
                db_copy = Path(tmp) / "bible.db"
                with archive.open(DB_ENTRY) as source, db_copy.open("wb") as target:
                    while chunk := source.read(1024 * 1024):
                        target.write(chunk)
                if not expected or _sha256(db_copy) != expected:
                    raise BackupError("백업 DB 해시가 일치하지 않습니다. 파일이 손상되었을 수 있습니다.")
                checks = _validate_sqlite(db_copy)
            return {"ok": True, "manifest": manifest, "checks": checks}
    except BackupError:
        raise
    except (zipfile.BadZipFile, OSError) as exc:
        raise BackupError(f"백업 ZIP을 읽을 수 없습니다: {exc}") from exc


def create_backup(db_path: Path, backups_dir: Path, app_version: str, reason: str = "manual") -> dict:
    db_path, backups_dir = Path(db_path), Path(backups_dir)
    if not db_path.is_file():
        raise BackupError("백업할 데이터베이스가 없습니다.")
    _validate_sqlite(db_path)
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    final_path = backups_dir / f"sermon_backup_{stamp}.zip"
    with tempfile.TemporaryDirectory(prefix="sermon-backup-create-", dir=backups_dir) as tmp:
        snapshot = Path(tmp) / "bible.db"
        try:
            with closing(sqlite3.connect(db_path)) as source:
                with closing(sqlite3.connect(snapshot)) as target:
                    source.backup(target)
        except sqlite3.DatabaseError as exc:
            raise BackupError(f"SQLite 백업 생성 실패: {exc}") from exc
        checks = _validate_sqlite(snapshot)
        manifest = {
            "format": BACKUP_FORMAT,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "app_version": str(app_version),
            "reason": reason,
            "database": {
                "entry": DB_ENTRY,
                "sha256": _sha256(snapshot),
                "size_bytes": snapshot.stat().st_size,
                "passages": checks["passages"],
                "sermons": checks["sermons"],
            },
        }
        partial = Path(tmp) / "backup.zip"
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr(MANIFEST_ENTRY, json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.write(snapshot, DB_ENTRY)
        os.replace(partial, final_path)
    return {"filename": final_path.name, "size_bytes": final_path.stat().st_size, "manifest": manifest}


def list_backups(backups_dir: Path) -> list[dict]:
    backups_dir = Path(backups_dir)
    backups_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(backups_dir.glob("sermon_backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            result = inspect_backup(path)
            manifest = result["manifest"]
            items.append({
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "created_at": manifest.get("created_at", ""),
                "app_version": manifest.get("app_version", ""),
                "reason": manifest.get("reason", ""),
                "passages": manifest.get("database", {}).get("passages", 0),
                "sermons": manifest.get("database", {}).get("sermons", 0),
                "valid": True,
            })
        except BackupError as exc:
            items.append({"filename": path.name, "size_bytes": path.stat().st_size, "valid": False, "error": str(exc)})
    return items


def restore_backup(backup_path: Path, db_path: Path, backups_dir: Path, app_version: str) -> dict:
    backup_path, db_path, backups_dir = Path(backup_path), Path(db_path), Path(backups_dir)
    inspected = inspect_backup(backup_path)
    pre_backup = create_backup(db_path, backups_dir, app_version, reason="pre_restore")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="restore-", suffix=".db", dir=db_path.parent)
    os.close(fd)
    replacement = Path(temp_name)
    try:
        with zipfile.ZipFile(backup_path, "r") as archive, archive.open(DB_ENTRY) as source, replacement.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
        _validate_sqlite(replacement)
        expected = inspected["manifest"]["database"]["sha256"]
        if _sha256(replacement) != expected:
            raise BackupError("복원 직전 DB 해시 재검사에 실패했습니다.")
        os.replace(replacement, db_path)
    finally:
        replacement.unlink(missing_ok=True)
    return {"restored": inspected, "pre_restore_backup": pre_backup}
