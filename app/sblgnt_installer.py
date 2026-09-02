"""Background installer for official SBLGNT and MorphGNT sources."""

from __future__ import annotations

import hashlib
import json
import threading
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from app.core import import_original_notes
from app.importers import convert_original_note_source
from app.paths import DATA_DIR
from app.sblgnt import SBLGNT_BOOK_FILENAMES, SBLGNT_ROOT, ensure_sblgnt_layout

SBLGNT_REPO = "https://raw.githubusercontent.com/Faithlife/SBLGNT/master"
MORPHGNT_REPO = "https://raw.githubusercontent.com/morphgnt/sblgnt/master"
SBLGNT_SOURCE = "https://github.com/LogosBible/SBLGNT"
MORPHGNT_SOURCE = "https://github.com/morphgnt/sblgnt"
SBLGNT_LICENSE = "CC BY 4.0 · SBLGNT v1.2 · Michael W. Holmes / Society of Biblical Literature and Logos Bible Software"
MORPHGNT_LICENSE = "MorphGNT source repository · attribution retained; see repository README"
MORPHGNT_FILES = (
    "61-Mt-morphgnt.txt", "62-Mk-morphgnt.txt", "63-Lk-morphgnt.txt", "64-Jn-morphgnt.txt",
    "65-Ac-morphgnt.txt", "66-Ro-morphgnt.txt", "67-1Co-morphgnt.txt", "68-2Co-morphgnt.txt",
    "69-Ga-morphgnt.txt", "70-Eph-morphgnt.txt", "71-Php-morphgnt.txt", "72-Col-morphgnt.txt",
    "73-1Th-morphgnt.txt", "74-2Th-morphgnt.txt", "75-1Ti-morphgnt.txt", "76-2Ti-morphgnt.txt",
    "77-Tit-morphgnt.txt", "78-Phm-morphgnt.txt", "79-Heb-morphgnt.txt", "80-Jas-morphgnt.txt",
    "81-1Pe-morphgnt.txt", "82-2Pe-morphgnt.txt", "83-1Jn-morphgnt.txt", "84-2Jn-morphgnt.txt",
    "85-3Jn-morphgnt.txt", "86-Jud-morphgnt.txt", "87-Re-morphgnt.txt",
)

_lock = threading.Lock()
_job = {"state": "idle", "percent": 0, "stage": "대기 중", "current": "", "message": "", "results": []}


def installer_status() -> dict:
    with _lock:
        return dict(_job, results=list(_job["results"]))


def _update(**values) -> None:
    with _lock:
        _job.update(values)


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "SermonLMStudio/40.9"})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read(60 * 1024 * 1024 + 1)
    if len(data) > 60 * 1024 * 1024:
        raise ValueError("원본 파일이 60MB 제한을 초과했습니다.")
    return data


def _write_atomic(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix(path.suffix + ".staging")
    staged.write_bytes(data)
    staged.replace(path)
    return hashlib.sha256(data).hexdigest()


def _install() -> None:
    ensure_sblgnt_layout()
    metadata_root = SBLGNT_ROOT / "metadata"
    morph_raw = DATA_DIR / "bible" / "greek_nt" / "morphgnt" / "raw"
    morph_raw.mkdir(parents=True, exist_ok=True)
    records = []
    total = 1 + len(SBLGNT_BOOK_FILENAMES) * 2 + len(MORPHGNT_FILES)
    done = imported = skipped = 0

    def step(label: str, url: str, target: Path, kind: str) -> bytes:
        nonlocal done
        _update(stage=label, current=target.name, message="공식 원본을 staging으로 내려받는 중입니다.", percent=round(done * 100 / total))
        data = _download(url)
        if not data.strip():
            raise ValueError(f"빈 파일입니다: {target.name}")
        if target.suffix.lower() == ".xml":
            ET.fromstring(data.decode("utf-8-sig"))
        checksum = _write_atomic(target, data)
        records.append({"file": target.name, "kind": kind, "path": str(target), "sha256": checksum, "bytes": len(data), "url": url})
        done += 1
        return data

    step("SBLGNT 전체 본문 검증", f"{SBLGNT_REPO}/data/sblgnt/xml/sblgnt.xml", SBLGNT_ROOT / "full" / "sblgnt.xml", "sblgnt_full")
    for book, filename in SBLGNT_BOOK_FILENAMES.items():
        step("SBLGNT 책별 본문 검증", f"{SBLGNT_REPO}/data/sblgnt/xml/{filename}", SBLGNT_ROOT / "books" / filename, f"sblgnt_book:{book}")
    for filename in SBLGNT_BOOK_FILENAMES.values():
        step("SBLGNT Apparatus 분리 저장", f"{SBLGNT_REPO}/data/sblgntapp/xml/{filename}", SBLGNT_ROOT / "apparatus" / filename, "apparatus")
    for filename in MORPHGNT_FILES:
        data = step("MorphGNT 형태론 검증·등록", f"{MORPHGNT_REPO}/{filename}", morph_raw / filename, "morphgnt_raw")
        _, items = convert_original_note_source(data.decode("utf-8-sig"), "morphgnt")
        for start in range(0, len(items), 4000):
            result = import_original_notes(items[start:start + 4000], MORPHGNT_SOURCE, MORPHGNT_LICENSE)
            imported += int(result.get("imported", 0))
            skipped += int(result.get("skipped_existing", 0))

    metadata_root.mkdir(parents=True, exist_ok=True)
    (metadata_root / "source.json").write_text(json.dumps({
        "source": "SBLGNT", "version": "v1.2", "license": SBLGNT_LICENSE,
        "source_url": SBLGNT_SOURCE, "retrieved_at": datetime.now(timezone.utc).isoformat(), "files": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (metadata_root / "ATTRIBUTION.md").write_text(
        f"# SBLGNT attribution\n\nThe Greek New Testament: SBL Edition (SBLGNT).\nEditor: Michael W. Holmes.\nLicense: CC BY 4.0.\nSource: {SBLGNT_SOURCE}\n\nMorphGNT source: {MORPHGNT_SOURCE}\n",
        encoding="utf-8",
    )
    _update(state="completed", percent=100, stage="설치 완료", current="", message="검증·저장·DB 등록이 모두 완료되었습니다.", results=[
        {"label": "SBLGNT 본문", "detail": f"전체 1개 + 책별 {len(SBLGNT_BOOK_FILENAMES)}개 저장"},
        {"label": "SBLGNT Apparatus", "detail": f"별도 파일 {len(SBLGNT_BOOK_FILENAMES)}개 저장"},
        {"label": "MorphGNT", "detail": f"{len(MORPHGNT_FILES)}개 파일 · 신규 DB {imported:,}건 · 중복 건너뜀 {skipped:,}건"},
        {"label": "라이선스·checksum", "detail": "metadata/source.json 및 ATTRIBUTION.md 기록 완료"},
    ])


def start_install() -> dict:
    with _lock:
        if _job["state"] == "running":
            return dict(_job)
        _job.update({"state": "running", "percent": 0, "stage": "설치 준비", "current": "", "message": "공식 자료 설치를 준비합니다.", "results": []})
    def runner():
        try:
            _install()
        except Exception as exc:
            _update(state="failed", stage="설치 중단", current="", message=str(exc), results=[])
    threading.Thread(target=runner, name="sblgnt-installer", daemon=True).start()
    return installer_status()
