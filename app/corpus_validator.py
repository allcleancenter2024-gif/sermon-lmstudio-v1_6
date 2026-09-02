"""Corpus validation for the installed SBLGNT source layer."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from app.importers import convert_bible_source
from app.sblgnt import SBLGNT_BOOK_FILENAMES, SBLGNT_ROOT
from app.references import parse_reference


def _issue(code: str, message: str, severity: str = "error", file: str | None = None) -> dict:
    result = {"code": code, "message": message, "severity": severity}
    if file:
        result["file"] = file
    return result


def validate_sblgnt_corpus(root: Path = SBLGNT_ROOT, metadata_path: Path | None = None, output_path: Path | None = None) -> dict:
    """Validate files and canonical verses without changing any source or DB data."""
    root, metadata_path = Path(root), metadata_path or Path(root) / "metadata" / "source.json"
    issues: list[dict] = []
    books: list[dict] = []
    metadata = {}
    if not metadata_path.is_file():
        issues.append(_issue("metadata_missing", "SBLGNT source.json이 없습니다.", file=str(metadata_path)))
    else:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(_issue("metadata_invalid", f"source.json을 읽을 수 없습니다: {exc}", file=str(metadata_path)))
    if metadata.get("license") and metadata.get("source_url"):
        attribution_status = "present"
    else:
        attribution_status = "missing"
        issues.append(_issue("attribution_incomplete", "license 또는 source_url metadata가 없습니다."))

    # Apparatus uses the same book filenames as SBLGNT, so the filename alone
    # is not a unique metadata key. Only compare against book-source entries.
    metadata_files = {
        item.get("file"): item for item in metadata.get("files", [])
        if isinstance(item, dict) and str(item.get("kind", "")).startswith("sblgnt_book")
    }
    seen_references: set[str] = set()
    for book_code, filename in SBLGNT_BOOK_FILENAMES.items():
        path = root / "books" / filename
        book_report = {"book": book_code, "file": filename, "status": "ok", "verses": 0, "sha256": None}
        if not path.is_file():
            book_report["status"] = "error"
            issues.append(_issue("book_missing", f"책별 XML이 없습니다: {filename}", file=str(path)))
            books.append(book_report)
            continue
        raw = path.read_bytes()
        book_report["sha256"] = hashlib.sha256(raw).hexdigest()
        if not raw.strip():
            book_report["status"] = "error"
            issues.append(_issue("book_empty", f"빈 책별 XML입니다: {filename}", file=str(path)))
            books.append(book_report)
            continue
        metadata_item = metadata_files.get(filename)
        if not metadata_item:
            issues.append(_issue("checksum_metadata_missing", f"checksum metadata가 없습니다: {filename}", "warning", str(path)))
        elif metadata_item.get("sha256") != book_report["sha256"]:
            book_report["status"] = "error"
            issues.append(_issue("checksum_mismatch", f"metadata checksum과 실제 파일이 다릅니다: {filename}", file=str(path)))
        try:
            _, passages = convert_bible_source(raw.decode("utf-8-sig"), "sblgnt_xml")
        except (UnicodeDecodeError, ValueError, ET.ParseError) as exc:
            book_report["status"] = "error"
            issues.append(_issue("xml_parse_error", f"책별 XML 파싱 실패: {exc}", file=str(path)))
            books.append(book_report)
            continue
        book_report["verses"] = len(passages)
        if not passages:
            book_report["status"] = "error"
            issues.append(_issue("book_has_no_verses", f"본문 구절이 없는 책별 XML입니다: {filename}", file=str(path)))
        local_refs: set[str] = set()
        for item in passages:
            reference = item.get("reference", "")
            if not item.get("text", "").strip():
                issues.append(_issue("verse_text_empty", f"본문이 비어 있습니다: {reference}", file=str(path)))
            try:
                parsed = parse_reference(reference)
                if parsed.book != book_code:
                    issues.append(_issue("book_code_mismatch", f"파일과 reference 책 코드가 다릅니다: {reference}", file=str(path)))
            except ValueError as exc:
                issues.append(_issue("reference_invalid", f"reference 해석 실패: {exc}", file=str(path)))
            if reference in local_refs or reference in seen_references:
                book_report["status"] = "error"
                issues.append(_issue("duplicate_reference", f"중복 canonical reference입니다: {reference}", file=str(path)))
            local_refs.add(reference)
            seen_references.add(reference)
        books.append(book_report)

    full_path = root / "full" / "sblgnt.xml"
    full_report = {"file": str(full_path), "status": "missing" if not full_path.is_file() else "ok", "verses": 0}
    if not full_path.is_file():
        issues.append(_issue("full_missing", "통합 sblgnt.xml이 없습니다.", file=str(full_path)))
    else:
        try:
            full_content = full_path.read_text(encoding="utf-8-sig")
            full_root = ET.fromstring(full_content)
            has_verse_nodes = any(isinstance(node.tag, str) and node.tag.rsplit("}", 1)[-1].lower() == "verse-number" for node in full_root.iter())
            if not has_verse_nodes:
                full_report["status"] = "metadata_shell"
                issues.append(_issue("full_has_no_verses", "통합 sblgnt.xml은 XML/라이선스 셸이며 본문 구절이 없습니다. 책별 XML을 runtime source로 사용합니다.", "warning", str(full_path)))
                full_items = []
            else:
                _, full_items = convert_bible_source(full_content, "sblgnt_xml")
            full_report["verses"] = len(full_items)
        except (OSError, ValueError, ET.ParseError) as exc:
            full_report["status"] = "error"
            issues.append(_issue("full_parse_error", f"통합 XML 파싱 실패: {exc}", file=str(full_path)))

    result = {
        "source": metadata.get("source", "SBLGNT"), "version": metadata.get("version", "unknown"),
        "expected_books": len(SBLGNT_BOOK_FILENAMES), "books_found": sum(1 for book in books if book["status"] != "missing"),
        "total_verses": sum(book["verses"] for book in books), "unique_references": len(seen_references),
        "attribution_status": attribution_status, "books": books, "full": full_report, "issues": issues,
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "policy": "validation_only_no_source_or_database_changes",
    }
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["output_path"] = str(output_path)
    return result
