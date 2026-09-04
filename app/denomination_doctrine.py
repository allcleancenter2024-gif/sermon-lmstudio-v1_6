"""Phase 2 safe source validation, local snapshotting, and change detection."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import os
import ipaddress
import json
from pathlib import Path
import re
import sqlite3
import socket
import tempfile
from urllib.parse import urlsplit
import urllib.error
import urllib.request

from app.paths import DATA_DIR
from app.doctrine_storage import LocalObjectStore, MinioObjectStore


MAX_DOCTRINE_DOWNLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_MIME_TYPES = {"text/html", "application/xhtml+xml", "application/pdf", "text/plain"}
OFFICIAL_HOST_ALLOWLIST = {
    "kmc.or.kr", "www.kmc.or.kr", "www.prok.org", "prok.org", "pcaac.org",
    "www.pcaac.org", "opc.org", "bfm.sbc.net", "sbc.net", "ag.org", "umc.org",
}
LICENSE_BLOCKED = {"UNKNOWN", "PERMISSION_REQUIRED", "BLOCKED"}
MAX_REDIRECTS = 3


def validate_official_url(url: str, allowlist: set[str] | None = None) -> str:
    parsed = urlsplit(str(url or "").strip())
    host = (parsed.hostname or "").casefold().rstrip(".")
    allowed = {x.casefold().rstrip(".") for x in (allowlist or OFFICIAL_HOST_ALLOWLIST)}
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in str(url)):
        raise ValueError("공식 자료원 URL에 제어문자를 사용할 수 없습니다.")
    if parsed.scheme.casefold() != "https":
        raise ValueError("공식 교리 자료원은 HTTPS URL만 사용할 수 있습니다.")
    if not host or host not in allowed:
        raise ValueError("공식 자료원 허용목록에 없는 호스트입니다.")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("공식 자료원 URL에 인증정보 또는 비표준 포트를 사용할 수 없습니다.")
    try:
        address = ipaddress.ip_address(host)
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            raise ValueError("사설·로컬·예약 IP 주소는 자료원으로 사용할 수 없습니다.")
    except ValueError as exc:
        if str(exc).startswith("사설·"):
            raise
    return parsed.geturl()


def validate_resolved_host(url: str, resolver=socket.getaddrinfo) -> None:
    host = urlsplit(url).hostname or ""
    try:
        infos = resolver(host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("공식 자료원 호스트의 DNS 확인에 실패했습니다.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast or address.is_unspecified:
            raise ValueError("자료원 호스트가 사설·로컬·예약 IP로 확인되어 차단되었습니다.")


def archive_object_key(code: str, source_id: int, edition: str, content_hash: str, extension: str) -> str:
    def safe(value: object, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip(".-")
        return cleaned[:120] or fallback
    digest = re.fullmatch(r"[0-9a-f]{64}", content_hash or "")
    if not digest:
        raise ValueError("원본 content_hash는 SHA-256 64자리 hex여야 합니다.")
    ext = re.sub(r"[^A-Za-z0-9]+", "", extension.lower()) or "bin"
    return f"doctrine-archive/{safe(code, 'UNKNOWN')}/{int(source_id)}/{safe(edition, 'undated')}/{content_hash}/original.{ext}"


def _mime_extension(mime: str) -> str:
    return {"text/html": "html", "application/xhtml+xml": "html", "application/pdf": "pdf", "text/plain": "txt"}.get(mime.split(";", 1)[0].casefold().strip(), "bin")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_official_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_official_source(url: str, opener=None, timeout: int = 20, request_headers: dict | None = None, resolver=socket.getaddrinfo) -> dict:
    validated = validate_official_url(url)
    validate_resolved_host(validated, resolver=resolver)
    headers = {"Accept": ", ".join(sorted(ALLOWED_MIME_TYPES)), **(request_headers or {})}
    request = urllib.request.Request(validated, headers=headers)
    client = opener or urllib.request.build_opener(_SafeRedirectHandler())
    try:
        with client.open(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
            if status == 304:
                return {"status": 304, "url": validated, "final_url": validated, "mime_type": "", "body": b"", "etag": response.headers.get("ETag", ""), "last_modified": response.headers.get("Last-Modified", "")}
            if status == 206:
                raise ValueError("부분 응답(206)은 전체 원본 보존 대상이 아니므로 거부했습니다.")
            final_url = validate_official_url(response.geturl())
            mime = (response.headers.get("Content-Type") or "").split(";", 1)[0].casefold().strip()
            if mime not in ALLOWED_MIME_TYPES:
                raise ValueError(f"허용되지 않은 MIME 유형입니다: {mime or '미상'}")
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_DOCTRINE_DOWNLOAD_BYTES:
                raise ValueError("교리 원본 파일이 50MB 제한을 초과합니다.")
            chunks, received = [], 0
            while True:
                chunk = response.read(min(64 * 1024, MAX_DOCTRINE_DOWNLOAD_BYTES - received + 1))
                if not chunk: break
                received += len(chunk)
                if received > MAX_DOCTRINE_DOWNLOAD_BYTES: raise ValueError("교리 원본 파일이 50MB 제한을 초과합니다.")
                chunks.append(chunk)
            body = b"".join(chunks)
            if len(body) > MAX_DOCTRINE_DOWNLOAD_BYTES:
                raise ValueError("교리 원본 파일이 50MB 제한을 초과합니다.")
            return {"status": status, "url": validated, "final_url": final_url, "mime_type": mime, "body": body,
                    "etag": response.headers.get("ETag", ""), "last_modified": response.headers.get("Last-Modified", "")}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"공식 자료원 HTTP 오류: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("공식 자료원에 연결하지 못했습니다.") from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def snapshot_source(source_id: int, db_path: Path, archive_root: Path = DATA_DIR, opener=None) -> dict:
    """Download one registered source, preserve an immutable local object, and record metadata."""
    with closing(sqlite3.connect(db_path)) as con:
        con.row_factory = sqlite3.Row
        source = con.execute(
            """SELECT s.*, d.code FROM doctrine_sources s JOIN denominations d ON d.id=s.denomination_id WHERE s.id=?""", (int(source_id),)
        ).fetchone()
    if not source:
        raise ValueError("등록된 교리 자료원을 찾지 못했습니다.")
    if not source["active"] or not source["denomination_id"]:
        raise ValueError("비활성 자료원은 수집할 수 없습니다.")
    if source["license_status"] in LICENSE_BLOCKED:
        raise ValueError("라이선스 확인 전 자료원은 자동 수집·색인할 수 없습니다.")
    job_time = _now()
    with closing(sqlite3.connect(db_path)) as con:
        con.row_factory = sqlite3.Row
        previous_snapshot = con.execute("SELECT * FROM source_snapshots WHERE source_id=? ORDER BY id DESC LIMIT 1", (int(source_id),)).fetchone()
    conditional = {}
    if previous_snapshot and previous_snapshot["etag"]:
        conditional["If-None-Match"] = previous_snapshot["etag"]
    elif previous_snapshot and previous_snapshot["last_modified"]:
        conditional["If-Modified-Since"] = previous_snapshot["last_modified"]
    with closing(sqlite3.connect(db_path)) as con, con:
        cur = con.execute("INSERT INTO ingestion_jobs(source_id,status,attempts,started_at) VALUES(?,?,?,?)", (int(source_id), "DOWNLOADING", 1, job_time))
        job_id = int(cur.lastrowid)
    try:
        result = download_official_source(source["source_url"], opener=opener, request_headers=conditional)
        if result.get("status") == 304 and previous_snapshot:
            with closing(sqlite3.connect(db_path)) as con, con:
                con.execute("UPDATE source_snapshots SET checked_at=?, request_url=?, final_url=?, etag=COALESCE(NULLIF(?,''),etag), last_modified=COALESCE(NULLIF(?,''),last_modified) WHERE id=?", (job_time, source["source_url"], result.get("final_url", source["source_url"]), result.get("etag", ""), result.get("last_modified", ""), previous_snapshot["id"]))
                con.execute("UPDATE ingestion_jobs SET status='UNCHANGED', finished_at=?, http_status=304, storage_status='EXISTING' WHERE id=?", (_now(), job_id))
            return {"job_id": job_id, "document_id": previous_snapshot["document_id"], "changed": False, "not_modified": True, "content_hash": previous_snapshot["content_hash"], "object_storage_key": previous_snapshot["object_storage_key"]}
        content_hash = hashlib.sha256(result["body"]).hexdigest()
        with closing(sqlite3.connect(db_path)) as con:
            previous = con.execute("SELECT id, content_hash FROM doctrine_documents WHERE source_id=? ORDER BY id DESC LIMIT 1", (int(source_id),)).fetchone()
        changed = not previous or previous[1] != content_hash
        key = archive_object_key(source["code"], source_id, "undated", content_hash, _mime_extension(result["mime_type"]))
        store = LocalObjectStore(archive_root)
        stored = store.put_bytes(key, result["body"], content_hash)
        minio_store = None
        if os.getenv('MINIO_ENABLED', '').strip().casefold() in {'1', 'true', 'yes', 'on'}:
            minio_store = MinioObjectStore.from_env()
            remote_prefix = os.getenv('MINIO_PROD_PREFIX', 'production/').strip('/') + '/'
            remote_key = f"{remote_prefix}{key}"
            minio_store.put_bytes(remote_key, result['body'], content_hash)
        object_path = archive_root / key.replace("/", "\\")
        metadata_key = f"{key.rsplit('/', 1)[0]}/metadata.json"
        metadata_payload = json.dumps({"source_id": source_id, "source_url": result["final_url"], "content_hash": content_hash, "mime_type": result["mime_type"], "retrieved_at": job_time}, ensure_ascii=False, indent=2).encode("utf-8")
        if changed and not object_path.with_name("metadata.json").exists():
            object_path.with_name("metadata.json").write_bytes(metadata_payload)
        if changed and minio_store and not minio_store.exists(f"{remote_prefix}{metadata_key}"):
            minio_store.put_bytes(f"{remote_prefix}{metadata_key}", metadata_payload, hashlib.sha256(metadata_payload).hexdigest())
        with closing(sqlite3.connect(db_path)) as con, con:
            document_id = None
            if changed:
                previous_document_id = previous[0] if previous and changed else None
                document_id = con.execute("""INSERT INTO doctrine_documents(source_id,title,language,content_hash,object_storage_key,mime_type,review_status,active,retrieved_at,supersedes_document_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (int(source_id), source["title"], "ko", content_hash, key, result["mime_type"], "DISCOVERED", 0, job_time, previous_document_id, job_time)).lastrowid
            con.execute("""INSERT INTO source_snapshots(source_id,document_id,checked_at,http_status,etag,last_modified,content_hash,object_storage_key,changed,request_url,final_url,mime_type,content_length,sha256_verified) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (int(source_id), document_id, job_time, 200, result["etag"], result["last_modified"], content_hash, key, int(changed), source["source_url"], result["final_url"], result["mime_type"], stored.size, 1))
            con.execute("UPDATE ingestion_jobs SET document_id=?,status=?,finished_at=?,http_status=?,storage_status=?,storage_key=?,bytes_received=?,error_category='' WHERE id=?", (document_id, "DOWNLOADED" if changed else "UNCHANGED", _now(), int(result.get("status", 200)), "STORED" if changed else "EXISTING", key, stored.size, job_id))
        return {"job_id": job_id, "document_id": document_id, "changed": changed, "content_hash": content_hash, "object_storage_key": key}
    except Exception as exc:
        with closing(sqlite3.connect(db_path)) as con, con:
            con.execute("UPDATE ingestion_jobs SET status='FAILED', error_code=?, error_category=?, error_summary=?, finished_at=? WHERE id=?", (type(exc).__name__, 'SECURITY' if isinstance(exc, ValueError) else 'DOWNLOAD', str(exc)[:500], _now(), job_id))
        raise
