from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


@contextmanager
def _connect(*args, **kwargs):
    """Commit or roll back a SQLite transaction, then always release its file handle."""
    con = sqlite3.connect(*args, **kwargs)
    try:
        with con:
            yield con
    finally:
        con.close()


MAX_NOTE_BYTES = 5 * 1024 * 1024
PACK_FORMAT = "sermon-notebooklm-pack-v1"


def init_notebooklm_db(db_path: Path) -> None:
    with _connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS external_research_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sermon_id INTEGER,
                reference TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'notebooklm',
                citations_json TEXT NOT NULL DEFAULT '[]',
                verification_status TEXT NOT NULL DEFAULT 'unverified',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_external_notes_reference
                ON external_research_notes(reference, created_at);
            CREATE TABLE IF NOT EXISTS notebooklm_packs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT NOT NULL,
                topic TEXT NOT NULL DEFAULT '',
                minutes INTEGER NOT NULL,
                filename TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                drive_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            """
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", value.strip()).strip("._")
    return slug[:80] or "sermon"


def get_drive_folder(db_path: Path) -> str:
    init_notebooklm_db(db_path)
    with _connect(db_path) as con:
        row = con.execute("SELECT value_json FROM app_settings WHERE key='notebooklm_drive_folder'").fetchone()
    if not row:
        return ""
    try:
        return str(json.loads(row[0]) or "")
    except (TypeError, json.JSONDecodeError):
        return ""


def set_drive_folder(folder: str, db_path: Path) -> dict:
    raw = str(folder or "").strip().strip('"')
    if not raw:
        with _connect(db_path) as con:
            con.execute("DELETE FROM app_settings WHERE key='notebooklm_drive_folder'")
        return {"folder": "", "ready": False, "message": "Google Drive 동기화 폴더 설정을 해제했습니다."}
    if raw.startswith(("\\\\", "//")):
        raise ValueError("네트워크 공유 경로가 아니라 이 PC의 Google Drive 동기화 폴더를 선택하세요.")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ValueError("Google Drive 폴더는 전체 경로로 입력하세요.")
    if not path.is_dir():
        raise ValueError("입력한 폴더가 없습니다. Google Drive 데스크톱의 실제 동기화 폴더를 확인하세요.")
    if not os.access(path, os.W_OK):
        raise ValueError("입력한 폴더에 파일을 쓸 권한이 없습니다.")
    probe = None
    try:
        fd, name = tempfile.mkstemp(prefix="sermon-drive-check-", dir=path)
        os.close(fd)
        probe = Path(name)
    except OSError as exc:
        raise ValueError(f"Google Drive 폴더 쓰기 시험에 실패했습니다: {exc}") from exc
    finally:
        if probe:
            probe.unlink(missing_ok=True)
    normalized = str(path.resolve())
    with _connect(db_path) as con:
        con.execute(
            """INSERT INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
            ("notebooklm_drive_folder", json.dumps(normalized, ensure_ascii=False), _now()),
        )
    return {"folder": normalized, "ready": True, "message": "쓰기 시험을 통과했습니다."}


def drive_status(db_path: Path) -> dict:
    folder = get_drive_folder(db_path)
    if not folder:
        return {"configured": False, "ready": False, "folder": "", "message": "동기화 폴더를 아직 설정하지 않았습니다."}
    path = Path(folder)
    ready = path.is_dir() and os.access(path, os.W_OK)
    return {
        "configured": True,
        "ready": ready,
        "folder": folder,
        "message": "로컬 동기화 폴더를 사용할 수 있습니다." if ready else "폴더가 없거나 쓸 수 없습니다. Google Drive 데스크톱 상태를 확인하세요.",
    }


def _items_markdown(title: str, items: list[dict], renderer) -> str:
    lines = [f"# {title}", ""]
    if not items:
        return "\n".join(lines + ["등록 자료 없음", ""])
    for item in items:
        lines.extend(renderer(item))
    return "\n".join(lines).strip() + "\n"


def build_pack_files(packet: dict, *, topic: str, reference: str, minutes: int, tradition: str) -> dict[str, str]:
    study = packet.get("study") or {}
    translations = list(study.get("translations") or [])
    originals = list(study.get("original_notes") or [])
    doctrine = list(packet.get("doctrine_sources") or [])
    source_lines = []
    for item in translations:
        source_lines.append(f"- {item.get('translation','자료')} · {item.get('reference','')} · {item.get('license_note','사용조건 미기록')}")
    for item in originals:
        source_lines.append(f"- 원어 {item.get('reference','')} · {item.get('source','출처 미기록')} · {item.get('license_note','사용조건 미기록')}")
    for item in doctrine:
        source_lines.append(f"- {item.get('title','교리 자료')} · {item.get('source_url','출처 URL 미기록')} · {item.get('license_note','사용조건 미기록')}")
    files = {
        "00_읽어주세요.md": f"""# Gemini Notebook 설교 연구 자료팩

- 주제: {topic or '미입력'}
- 중심본문: {reference}
- 설교 시간: {minutes}분
- 신학적 전통: {tradition}

이 자료팩은 등록된 로컬 자료만 포함합니다. Gemini Notebook의 답변은 연구 보조자료이며 원어·번역 해석의 최종 증거가 아닙니다. 답변의 인용을 확인한 뒤 설교 작성기로 가져오세요.
""",
        "01_중심본문.md": _items_markdown("중심본문과 번역 비교", translations, lambda x: [f"## {x.get('translation','자료')} · {x.get('reference','')}", str(x.get('text','')), f"- 사용조건: {x.get('license_note','미기록')}", ""]),
        "02_원어연구.md": _items_markdown("히브리어·헬라어 원어 연구", originals, lambda x: [f"## {x.get('reference','')} · {x.get('lemma','')}", f"- 언어: {x.get('language','')}", f"- 음역: {x.get('transliteration','미기록')}", f"- 뜻: {x.get('gloss','미기록')}", f"- 형태·문법: {x.get('morphology','미기록')}", f"- 출처: {x.get('source','미기록')}", f"- 사용조건: {x.get('license_note','미기록')}", ""]),
        "03_번역비교.md": "# 권장 분석 순서\n\n개역개정 → 히브리어/헬라어 → ESV/NASB → NIV/CSB → NET 번역주석 → NLT → 주석·신앙고백 문서\n\nAMP와 The Message는 표현 이해 보조로만 사용합니다.\n\n" + (packet.get("study", {}).get("note_markdown") or ""),
        "04_교리주석.md": _items_markdown("등록 교리·주석 근거", doctrine, lambda x: [f"## {x.get('title','교리 자료')} · {x.get('section','')}", str(x.get('text','')), f"- 출처: {x.get('source_url','미기록')}", f"- 사용조건: {x.get('license_note','미기록')}", ""]),
        "05_연구질문.md": f"""# Gemini Notebook에 입력할 연구 질문

업로드된 자료만 근거로 답해주세요. {reference}의 핵심 메시지를 개역개정, 원문, ESV/NASB, NIV/CSB, NET 번역주석 순서로 분석하고 각 주장 뒤에 인용을 표시해주세요. 자료에 없으면 ‘자료에서 확인되지 않음’이라고 표시해주세요.

1. 원문의 핵심 lemma와 문맥상 의미는 무엇입니까?
2. ESV와 NASB가 문장 구조를 다르게 드러내는 부분은 무엇입니까?
3. NIV와 CSB가 현대 독자에게 의미를 어떻게 전달합니까?
4. NET 번역주석의 본문 쟁점은 무엇입니까?
5. 자료에 근거한 {minutes}분 설교의 핵심 메시지와 3대지 후보를 제시해주세요.
""",
        "06_출처목록.md": "# 출처와 사용조건\n\n" + ("\n".join(source_lines) if source_lines else "등록 출처 없음") + "\n",
    }
    return files


def create_pack(packet: dict, *, topic: str, reference: str, minutes: int, tradition: str,
                exports_dir: Path, db_path: Path, sync_to_drive: bool = False) -> dict:
    init_notebooklm_db(db_path)
    exports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"NotebookLM_{_safe_slug(reference)}_{minutes}분_{stamp}.zip"
    final_path = exports_dir / filename
    files = build_pack_files(packet, topic=topic, reference=reference, minutes=minutes, tradition=tradition)
    manifest = {
        "format": PACK_FORMAT, "created_at": _now(), "topic": topic, "reference": reference,
        "minutes": minutes, "tradition": tradition, "files": sorted([*files, "manifest.json"]),
        "notice": "Notebook 결과는 외부 연구노트로 분리 저장하고 목회자가 인용을 확인해야 합니다.",
    }
    with tempfile.TemporaryDirectory(prefix="notebooklm-pack-", dir=exports_dir) as tmp:
        root = Path(tmp)
        for name, content in files.items():
            (root / name).write_text(content, encoding="utf-8")
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        partial = root / "pack.zip"
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in manifest["files"]:
                archive.write(root / name, name)
        os.replace(partial, final_path)
    digest = hashlib.sha256(final_path.read_bytes()).hexdigest()
    drive_path = ""
    drive_warning = ""
    if sync_to_drive:
        status = drive_status(db_path)
        if status["ready"]:
            target_dir = Path(status["folder"]) / "SermonLMStudio" / "NotebookLM"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / filename
            temp_target = target.with_suffix(target.suffix + ".partial")
            shutil.copy2(final_path, temp_target)
            if hashlib.sha256(temp_target.read_bytes()).hexdigest() != digest:
                temp_target.unlink(missing_ok=True)
                raise ValueError("Google Drive 폴더 복사 후 파일 검증에 실패했습니다. 로컬 자료팩은 보존되었습니다.")
            os.replace(temp_target, target)
            drive_path = str(target)
        else:
            drive_warning = status["message"]
    with _connect(db_path) as con:
        con.execute(
            "INSERT INTO notebooklm_packs(reference, topic, minutes, filename, sha256, drive_path, created_at) VALUES(?,?,?,?,?,?,?)",
            (reference, topic, minutes, filename, digest, drive_path, _now()),
        )
    return {"filename": filename, "path": str(final_path), "sha256": digest, "drive_path": drive_path, "drive_warning": drive_warning, "files": manifest["files"]}


def import_research_note(*, reference: str, title: str, content: str, sermon_id: int | None,
                         db_path: Path) -> dict:
    init_notebooklm_db(db_path)
    encoded = content.encode("utf-8")
    if not content.strip():
        raise ValueError("가져올 연구 결과가 비어 있습니다.")
    if len(encoded) > MAX_NOTE_BYTES:
        raise ValueError("연구 결과는 최대 5MB까지 가져올 수 있습니다.")
    citation_patterns = [r"\[[0-9]+\]", r"【[^】]+】", r"https?://\S+", r"출처\s*[:：]"]
    citations = []
    for pattern in citation_patterns:
        citations.extend(re.findall(pattern, content, flags=re.IGNORECASE))
    citations = list(dict.fromkeys(citations))[:100]
    status = "needs_review" if citations else "unverified"
    with _connect(db_path) as con:
        cur = con.execute(
            """INSERT INTO external_research_notes
               (sermon_id, reference, title, content, source_type, citations_json, verification_status, created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (sermon_id, reference.strip(), title.strip() or "Gemini Notebook 연구노트", content,
             "notebooklm", json.dumps(citations, ensure_ascii=False), status, _now()),
        )
    return {"id": int(cur.lastrowid), "reference": reference, "title": title, "citation_count": len(citations), "verification_status": status}


def list_research_notes(reference: str, db_path: Path) -> list[dict]:
    init_notebooklm_db(db_path)
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT id, sermon_id, reference, title, source_type, citations_json, verification_status, created_at FROM external_research_notes WHERE reference=? ORDER BY id DESC",
            (reference.strip(),),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["citation_count"] = len(json.loads(item.pop("citations_json") or "[]"))
        result.append(item)
    return result
