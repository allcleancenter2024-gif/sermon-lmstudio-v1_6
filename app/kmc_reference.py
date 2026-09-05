"""KMC official URL references that are never treated as copied evidence text."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import socket
import urllib.error
import urllib.request

from app.denomination_doctrine import validate_official_url, validate_resolved_host


def fetch_kmc_reference_sources(db_path: Path) -> list[dict]:
    """Return metadata-only KMC references; restricted sources are not indexable."""
    with closing(sqlite3.connect(db_path)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """SELECT n.code AS denomination, n.name_ko AS denomination_ko,
                      s.id, s.title, s.document_type, s.source_url,
                      s.source_authority, s.license_status, s.active,
                      s.permission_ref, s.license_review_note
               FROM doctrine_sources s JOIN denominations n ON n.id=s.denomination_id
               WHERE n.code='KMC' AND s.document_type IN ('doctrine_web_reference','constitution_web_reference')
               ORDER BY s.id"""
        ).fetchall()
    return [{
        "source_id": f"kmc-reference-{row['id']}", "source_type": "official_web_reference",
        "source_name": row["title"], "reference": row["title"], "text": "",
        "url": row["source_url"], "denomination": row["denomination"],
        "denomination_ko": row["denomination_ko"], "authority_level": "official_primary",
        "copyright_status": row["license_status"], "active": bool(row["active"]),
        "indexable": False, "reference_only": True, "permission_ref": row["permission_ref"],
        "license_review_note": row["license_review_note"],
    } for row in rows]


def compare_kmc_reference_metadata(db_path: Path) -> dict:
    """Compare KMC edition inventories without downloading or reading source text."""
    with closing(sqlite3.connect(db_path)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """SELECT s.id, s.title, s.document_type, s.source_url, s.license_status,
                      s.active, s.permission_ref, s.license_review_note
               FROM doctrine_sources s JOIN denominations n ON n.id=s.denomination_id
               WHERE n.code='KMC' AND s.document_type IN ('doctrine_web_reference','constitution_web_reference')
               ORDER BY s.title, s.id"""
        ).fetchall()
    items = []
    for row in rows:
        title = str(row['title'] or '').strip()
        source_url = str(row['source_url'] or '')
        edition = '2021' if '2021' in f'{title} {source_url}' else '2025' if '2025' in f'{title} {source_url}' else 'unknown'
        items.append({
            'id': int(row['id']), 'edition': edition, 'title': title,
            'document_type': row['document_type'], 'url': source_url,
            'copyright_status': row['license_status'], 'active': bool(row['active']),
            'indexable': False, 'reference_only': True,
            'permission_ref': row['permission_ref'], 'license_review_note': row['license_review_note'],
        })
    by_edition = {edition: [x for x in items if x['edition'] == edition] for edition in ('2021', '2025')}
    titles_2021 = {x['title'] for x in by_edition['2021']}
    titles_2025 = {x['title'] for x in by_edition['2025']}
    return {
        'denomination': 'KMC', 'comparison_type': 'metadata_inventory',
        'text_compared': False, 'download_performed': False, 'indexable': False,
        'editions': {k: {'count': len(v), 'items': v} for k, v in by_edition.items()},
        'added_in_2025': sorted(titles_2025 - titles_2021),
        'removed_after_2021': sorted(titles_2021 - titles_2025),
        'unchanged_title_count': len(titles_2021 & titles_2025),
        'status': 'reference_only',
    }


def probe_kmc_reference_headers(db_path: Path, *, opener=None, resolver=socket.getaddrinfo, timeout: int = 15) -> dict:
    """Probe official KMC pages without reading or storing response bodies."""
    references = fetch_kmc_reference_sources(db_path)
    results = []
    client = opener or urllib.request.build_opener()
    with closing(sqlite3.connect(db_path)) as con, con:
        con.execute('''CREATE TABLE IF NOT EXISTS kmc_reference_baselines (
            source_id TEXT PRIMARY KEY, url TEXT NOT NULL, final_url TEXT NOT NULL DEFAULT '',
            http_status INTEGER NOT NULL DEFAULT 0, etag TEXT NOT NULL DEFAULT '',
            last_modified TEXT NOT NULL DEFAULT '', content_length TEXT NOT NULL DEFAULT '',
            checked_at TEXT NOT NULL, changed INTEGER NOT NULL DEFAULT 0
        )''')
        con.execute('''CREATE TABLE IF NOT EXISTS kmc_reference_check_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL, url TEXT NOT NULL,
            final_url TEXT NOT NULL DEFAULT '', http_status INTEGER NOT NULL DEFAULT 0,
            etag TEXT NOT NULL DEFAULT '', last_modified TEXT NOT NULL DEFAULT '',
            content_length TEXT NOT NULL DEFAULT '', checked_at TEXT NOT NULL,
            changed INTEGER, result_status TEXT NOT NULL, body_read INTEGER NOT NULL DEFAULT 0
        )''')
        con.execute('''CREATE TABLE IF NOT EXISTS kmc_reference_review_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL, reviewer TEXT NOT NULL,
            decision TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '', decided_at TEXT NOT NULL
        )''')
    for reference in references:
        url = validate_official_url(reference['url'])
        validate_resolved_host(url, resolver=resolver)
        request = urllib.request.Request(url, method='HEAD', headers={'Accept': 'text/html', 'User-Agent': 'SermonLMStudio-KMC-Reference/1.0'})
        try:
            with client.open(request, timeout=timeout) as response:
                final_url = validate_official_url(response.geturl())
                etag = response.headers.get('ETag', '')
                last_modified = response.headers.get('Last-Modified', '')
                content_length = response.headers.get('Content-Length', '')
                checked_at = datetime.now(timezone.utc).isoformat()
                with closing(sqlite3.connect(db_path)) as con, con:
                    previous = con.execute('SELECT url,final_url,http_status,etag,last_modified,content_length FROM kmc_reference_baselines WHERE source_id=?', (reference['source_id'],)).fetchone()
                    changed = bool(previous and previous != (url, final_url, int(getattr(response, 'status', 200) or 200), etag, last_modified, content_length))
                    con.execute('''INSERT INTO kmc_reference_baselines(source_id,url,final_url,http_status,etag,last_modified,content_length,checked_at,changed)
                        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET url=excluded.url,final_url=excluded.final_url,http_status=excluded.http_status,etag=excluded.etag,last_modified=excluded.last_modified,content_length=excluded.content_length,checked_at=excluded.checked_at,changed=excluded.changed''', (reference['source_id'], url, final_url, int(getattr(response, 'status', 200) or 200), etag, last_modified, content_length, checked_at, int(changed)))
                    con.execute('''INSERT INTO kmc_reference_check_logs(source_id,url,final_url,http_status,etag,last_modified,content_length,checked_at,changed,result_status,body_read) VALUES(?,?,?,?,?,?,?,?,?,?,0)''', (reference['source_id'], url, final_url, int(getattr(response, 'status', 200) or 200), etag, last_modified, content_length, checked_at, int(changed), 'checked'))
                results.append({
                    'source_id': reference['source_id'], 'title': reference['source_name'],
                    'url': url, 'final_url': final_url, 'http_status': int(getattr(response, 'status', 200) or 200),
                    'etag': etag, 'last_modified': last_modified, 'content_length': content_length,
                    'body_read': False, 'changed': changed, 'status': 'checked',
                })
        except urllib.error.HTTPError as exc:
            checked_at = datetime.now(timezone.utc).isoformat()
            with closing(sqlite3.connect(db_path)) as con, con:
                con.execute('INSERT INTO kmc_reference_check_logs(source_id,url,http_status,checked_at,changed,result_status,body_read) VALUES(?,?,?,?,?,?,0)', (reference['source_id'], url, int(exc.code), checked_at, None, 'http_error'))
            results.append({'source_id': reference['source_id'], 'title': reference['source_name'], 'url': url, 'http_status': int(exc.code), 'body_read': False, 'changed': None, 'status': 'http_error'})
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            checked_at = datetime.now(timezone.utc).isoformat()
            with closing(sqlite3.connect(db_path)) as con, con:
                con.execute('INSERT INTO kmc_reference_check_logs(source_id,url,checked_at,changed,result_status,body_read) VALUES(?,?,?,?,?,0)', (reference['source_id'], url, checked_at, None, 'probe_failed'))
            results.append({'source_id': reference['source_id'], 'title': reference['source_name'], 'url': url, 'body_read': False, 'changed': None, 'status': 'probe_failed', 'error': str(exc)[:300]})
    return {'denomination': 'KMC', 'probe_type': 'HEAD_METADATA_ONLY', 'body_read': False, 'download_performed': False, 'indexable': False, 'results': results}


def list_kmc_reference_check_logs(db_path: Path, limit: int = 30) -> list[dict]:
    """Return only auditable HEAD metadata; never expose source content."""
    safe_limit = max(1, min(int(limit), 100))
    with closing(sqlite3.connect(db_path)) as con:
        con.row_factory = sqlite3.Row
        table = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='kmc_reference_check_logs'").fetchone()
        if not table:
            return []
        rows = con.execute('''SELECT source_id,url,final_url,http_status,etag,last_modified,
            content_length,checked_at,changed,result_status,body_read
            FROM kmc_reference_check_logs ORDER BY id DESC LIMIT ?''', (safe_limit,)).fetchall()
    return [dict(row) for row in rows]


def kmc_reference_review_gate(db_path: Path) -> dict:
    """Return a non-bypassable review gate for changed or failed probes."""
    logs = list_kmc_reference_check_logs(db_path, 100)
    latest = {}
    for item in logs:
        latest.setdefault(item['source_id'], item)
    attention = [item for item in latest.values() if bool(item.get('changed')) or item.get('result_status') != 'checked']
    return {
        'ready_for_automatic_processing': False,
        'review_required': bool(attention),
        'automatic_download_allowed': False,
        'automatic_indexing_allowed': False,
        'items': attention,
        'reason': 'KMC 공식 자료원은 Reference-only 정책으로 원문 자동 처리를 허용하지 않습니다.' if not attention else '변경 또는 점검 오류 자료원이 있어 관리자 검토가 필요합니다.',
    }


def build_kmc_operational_report(db_path: Path) -> dict:
    """Build a metadata-only operational report suitable for backup/audit review."""
    return {
        'report_type': 'KMC_REFERENCE_OPERATIONAL_METADATA',
        'comparison': compare_kmc_reference_metadata(db_path),
        'review_gate': kmc_reference_review_gate(db_path),
        'recent_checks': list_kmc_reference_check_logs(db_path, 30),
        'content_included': False,
        'original_files_included': False,
        'download_performed': False,
        'indexing_performed': False,
    }


def record_kmc_review_decisions(db_path: Path, reviewer: str, decision: str, comment: str = '') -> dict:
    if decision not in {'ACKNOWLEDGED', 'REJECTED'}:
        raise ValueError('KMC 검토 결정은 ACKNOWLEDGED 또는 REJECTED만 사용할 수 있습니다.')
    gate = kmc_reference_review_gate(db_path)
    decided_at = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(db_path)) as con, con:
        con.execute('''CREATE TABLE IF NOT EXISTS kmc_reference_review_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL, reviewer TEXT NOT NULL,
            decision TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '', decided_at TEXT NOT NULL
        )''')
        for item in gate['items']:
            con.execute('INSERT INTO kmc_reference_review_decisions(source_id,reviewer,decision,comment,decided_at) VALUES(?,?,?,?,?)', (item['source_id'], reviewer.strip(), decision, comment.strip()[:2000], decided_at))
    return {'recorded': len(gate['items']), 'decision': decision, 'reviewer': reviewer.strip(), 'decided_at': decided_at, 'automatic_download_allowed': False, 'automatic_indexing_allowed': False}


def build_kmc_final_checklist(db_path: Path) -> dict:
    report = build_kmc_operational_report(db_path)
    gate = report['review_gate']
    checks = {
        'reference_inventory_available': bool(report['comparison']['editions']),
        'baseline_available': bool(report['recent_checks']),
        'audit_history_available': bool(report['recent_checks']),
        'review_gate_enforced': gate['ready_for_automatic_processing'] is False,
        'content_excluded': report['content_included'] is False,
        'original_files_excluded': report['original_files_included'] is False,
        'automatic_processing_blocked': gate['automatic_download_allowed'] is False and gate['automatic_indexing_allowed'] is False,
    }
    return {'checklist_type': 'KMC_REFERENCE_FINAL_OPERATIONS', 'checks': checks, 'safety_controls_ready': all(checks.values()), 'operational_ready': all(checks.values()) and not gate['review_required'], 'review_required': gate['review_required'], 'automatic_download_allowed': False, 'automatic_indexing_allowed': False, 'next_action': '관리자 검토 및 정책에 따른 수동 절차 확인' if gate['review_required'] else '정기 HEAD 점검 유지'}
