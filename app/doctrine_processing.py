"""Phase 3 extraction, quality gates, and deterministic doctrine chunking."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
from html.parser import HTMLParser
from typing import Protocol

from app.paths import DATA_DIR
from app.doctrine_backend import DoctrineBackend
from app.doctrine_backend import create_doctrine_backend
from app.doctrine_ocr import DoctrineOcrProvider, validate_ocr_result


class DoctrineQualityError(ValueError):
    """Raised when extracted content is not safe to index yet."""


class DoctrineObjectReader(Protocol):
    def get_bytes(self, key: str) -> bytes: ...


@dataclass(frozen=True)
class DoctrineBlock:
    section_path: str
    article_number: str
    article_title: str
    text: str


class _DoctrineHTMLParser(HTMLParser):
    _SKIP = {"script", "style", "nav", "footer", "aside", "form"}
    _HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.current_tag = ""
        self.buffer: list[str] = []
        self.blocks: list[DoctrineBlock] = []
        self.headings: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.casefold()
        if tag in self._SKIP:
            self.skip_depth += 1
        if tag in self._HEADINGS or tag in {"p", "li"}:
            self.current_tag = tag
            self.buffer = []

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if tag in self._SKIP and self.skip_depth:
            self.skip_depth -= 1
        if tag == self.current_tag:
            text = re.sub(r"\s+", " ", html.unescape("".join(self.buffer))).strip()
            if text:
                if tag in self._HEADINGS:
                    self.headings.append(text)
                    number = (re.match(r"^(?:제\s*)?([0-9]+(?:[-.][0-9]+)*)[.)]?\s*", text) or ["", ""])[1]
                    title = re.sub(r"^(?:제\s*)?[0-9]+(?:[-.][0-9]+)*[.)]?\s*", "", text).strip() or text
                    self.blocks.append(DoctrineBlock(" > ".join(self.headings), number, title, text))
                else:
                    path = " > ".join(self.headings)
                    self.blocks.append(DoctrineBlock(path, "", "", text))
            self.current_tag = ""
            self.buffer = []

    def handle_data(self, data):
        if not self.skip_depth and self.current_tag:
            self.buffer.append(data)


def extract_html(content: str) -> list[DoctrineBlock]:
    parser = _DoctrineHTMLParser()
    parser.feed(str(content or ""))
    parser.close()
    return parser.blocks


def extract_plain_text(content: str) -> list[DoctrineBlock]:
    text = re.sub(r"\s+", " ", str(content or "")).strip()
    return [DoctrineBlock("", "", "", text)] if text else []


def extract_pdf(content: bytes) -> list[DoctrineBlock]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DoctrineQualityError("PDF 텍스트 추출 모듈이 설치되지 않아 검토 대기 상태로 남깁니다.") from exc
    try:
        reader = PdfReader(__import__("io").BytesIO(content))
        blocks = []
        for page_no, page in enumerate(reader.pages, 1):
            text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
            if text:
                blocks.append(DoctrineBlock(f"페이지 {page_no}", "", "", text))
        if not blocks:
            raise DoctrineQualityError("PDF에서 텍스트를 추출하지 못했습니다. 스캔 문서일 수 있어 OCR 검토가 필요합니다.")
        return blocks
    except Exception as exc:
        raise DoctrineQualityError(f"PDF 텍스트 추출에 실패했습니다: {exc}") from exc


def quality_gate(blocks: list[DoctrineBlock], minimum_chars: int = 80) -> dict:
    text = "\n".join(block.text for block in blocks).strip()
    replacement_count = text.count("�")
    control_count = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    reasons = []
    if len(text) < minimum_chars:
        reasons.append(f"추출 본문이 최소 {minimum_chars}자보다 짧습니다.")
    if replacement_count and replacement_count / max(len(text), 1) > 0.01:
        reasons.append("문자 깨짐 비율이 1%를 초과합니다.")
    if control_count:
        reasons.append("제어 문자가 포함되어 있습니다.")
    if not blocks:
        reasons.append("추출된 본문 블록이 없습니다.")
    return {"passed": not reasons, "characters": len(text), "blocks": len(blocks), "headings": sum(bool(b.article_title) for b in blocks), "reasons": reasons}


def _tokens(text: str) -> list[str]:
    return re.findall(r"\S+", text.strip())


def chunk_doctrine_blocks(blocks: list[DoctrineBlock], target_tokens: int = 550, overlap_tokens: int = 80) -> list[dict]:
    if target_tokens < 100 or overlap_tokens < 0 or overlap_tokens >= target_tokens:
        raise ValueError("청킹 token 설정이 올바르지 않습니다.")
    result = []
    for block in blocks:
        words = _tokens(block.text)
        if not words:
            continue
        start = 0
        while start < len(words):
            end = min(len(words), start + target_tokens)
            text = " ".join(words[start:end])
            result.append({
                "section_path": block.section_path,
                "article_number": block.article_number,
                "article_title": block.article_title,
                "chunk_index": len(result),
                "content": text,
                "token_count": end - start,
                "scripture_refs": sorted(set(re.findall(r"\b(?:[1-3]\s*)?[A-Z][A-Za-z]+\s+\d+[:.]\d+(?:[-–]\d+)?", text))),
                "topic_tags": [],
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            })
            if end == len(words):
                break
            start = end - overlap_tokens
    return result


def read_document_processing_metadata(document_id: int, db_path: Path, backend: DoctrineBackend | None = None, connection=None) -> dict:
    """Read document metadata through the selected doctrine backend."""
    if backend is not None and backend.name == "postgres":
        if connection is not None:
            return backend.repository.get_document_metadata(connection, int(document_id))
        with backend.adapter.transaction() as con:
            return backend.repository.get_document_metadata(con, int(document_id))
    with closing(sqlite3.connect(db_path)) as con:
        row = con.execute("SELECT metadata_json FROM doctrine_documents WHERE id=?", (int(document_id),)).fetchone()
    if not row:
        raise ValueError("처리할 교리 문서를 찾지 못했습니다.")
    return json.loads(row[0] or "{}")


def read_document_for_processing(document_id: int, db_path: Path, backend: DoctrineBackend | None = None) -> dict:
    """Read processing fields through the selected doctrine backend."""
    if backend is not None and backend.name == "postgres":
        with backend.adapter.transaction() as con:
            return backend.repository.get_document_for_processing(con, int(document_id))
    with closing(sqlite3.connect(db_path)) as con:
        con.row_factory = sqlite3.Row
        columns = {row[1] for row in con.execute("PRAGMA table_info(doctrine_documents)")}
        hash_column = "content_hash" if "content_hash" in columns else "'' AS content_hash"
        row = con.execute(f"SELECT id, object_storage_key, {hash_column}, mime_type, review_status, active FROM doctrine_documents WHERE id=?",
                          (int(document_id),)).fetchone()
    if not row:
        raise ValueError("처리할 교리 문서를 찾지 못했습니다.")
    return dict(row)


def write_document_processing_metadata(document_id: int, metadata: dict, db_path: Path,
                                      backend: DoctrineBackend | None = None, connection=None) -> None:
    """Write document metadata through the selected backend without changing status."""
    if backend is not None and backend.name == "postgres":
        if connection is not None:
            backend.repository.set_document_metadata(connection, int(document_id), metadata)
            return
        with backend.adapter.transaction() as con:
            backend.repository.set_document_metadata(con, int(document_id), metadata)
        return
    with closing(sqlite3.connect(db_path)) as con, con:
        con.execute("UPDATE doctrine_documents SET metadata_json=? WHERE id=?",
                    (json.dumps(metadata, ensure_ascii=False), int(document_id)))


def write_document_review_state(document_id: int, review_status: str, active: bool, db_path: Path,
                                backend: DoctrineBackend | None = None, connection=None) -> None:
    """Update review state through the selected doctrine backend."""
    if backend is not None and backend.name == "postgres":
        if connection is not None:
            backend.repository.update_review_state(connection, int(document_id), review_status, active)
            return
        with backend.adapter.transaction() as con:
            backend.repository.update_review_state(con, int(document_id), review_status, active)
        return
    with closing(sqlite3.connect(db_path)) as con, con:
        con.execute("UPDATE doctrine_documents SET review_status=?, active=? WHERE id=?",
                    (review_status, int(bool(active)), int(document_id)))


def process_doctrine_document(document_id: int, db_path: Path, archive_root: Path = DATA_DIR,
                              backend: DoctrineBackend | None = None,
                              object_store: DoctrineObjectReader | None = None,
                              object_prefix: str = "",
                              ocr_provider: DoctrineOcrProvider | None = None) -> dict:
    document = read_document_for_processing(document_id, db_path, backend=backend)
    object_key = str(document["object_storage_key"])
    path = archive_root / object_key.replace("/", "\\")
    try:
        remote_key = object_prefix.strip("/") + "/" + object_key.lstrip("/") if object_prefix.strip("/") else object_key
        raw = object_store.get_bytes(remote_key) if object_store is not None else path.read_bytes()
        expected_hash = str(document.get("content_hash", ""))
        if expected_hash and hashlib.sha256(raw).hexdigest() != expected_hash:
            raise DoctrineQualityError("원본 객체 SHA-256이 문서 metadata와 일치하지 않습니다.")
        if document["mime_type"] == "application/pdf":
            try:
                blocks = extract_pdf(raw)
            except DoctrineQualityError as exc:
                if ocr_provider is None or "OCR" not in str(exc):
                    raise
                ocr_result = ocr_provider.extract(raw, "application/pdf")
                validate_ocr_result(ocr_result)
                blocks = extract_plain_text(ocr_result.text)
        elif document["mime_type"] in {"text/html", "application/xhtml+xml"}:
            blocks = extract_html(raw.decode("utf-8", errors="replace"))
        else:
            blocks = extract_plain_text(raw.decode("utf-8", errors="replace"))
        quality = quality_gate(blocks)
        if not quality["passed"]:
            raise DoctrineQualityError("; ".join(quality["reasons"]))
        chunks = chunk_doctrine_blocks(blocks)
        metadata = {"quality": quality, "chunk_count": len(chunks)}
        if backend is not None:
            with backend.adapter.transaction() as con:
                backend.chunk_repository.replace_chunks(con, int(document_id), chunks)
                backend.repository.update_review_state(con, int(document_id), "NEEDS_REVIEW", False)
                backend.repository.set_document_metadata(con, int(document_id), metadata)
        else:
            with closing(sqlite3.connect(db_path)) as con, con:
                con.execute("PRAGMA foreign_keys=ON")
                create_doctrine_backend(database_path=db_path, environ={"DB_BACKEND": "existing"}).chunk_repository.replace_chunks(con, int(document_id), chunks)
            write_document_review_state(document_id, "NEEDS_REVIEW", False, db_path)
            write_document_processing_metadata(document_id, metadata, db_path)
        return {"document_id": document_id, "quality": quality, "chunks": len(chunks), "review_status": "NEEDS_REVIEW"}
    except DoctrineQualityError as exc:
        metadata = {"quality_error": str(exc)}
        if backend is not None:
            with backend.adapter.transaction() as con:
                backend.repository.update_review_state(con, int(document_id), "NEEDS_REVIEW", False)
                backend.repository.set_document_metadata(con, int(document_id), metadata)
        else:
            write_document_review_state(document_id, "NEEDS_REVIEW", False, db_path)
            write_document_processing_metadata(document_id, metadata, db_path)
        return {"document_id": document_id, "quality": {"passed": False, "reasons": [str(exc)]}, "chunks": 0, "review_status": "NEEDS_REVIEW"}
