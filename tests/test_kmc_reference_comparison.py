import sqlite3

from app.kmc_reference import compare_kmc_reference_metadata, kmc_reference_review_gate, probe_kmc_reference_headers
from app.backup import create_backup, restore_backup
from app.core import init_db


def test_kmc_reference_comparison_is_metadata_only(tmp_path):
    db = tmp_path / 'kmc.sqlite3'
    con = sqlite3.connect(db)
    con.executescript('''
      CREATE TABLE denominations(id INTEGER PRIMARY KEY, code TEXT, name_ko TEXT);
      CREATE TABLE doctrine_sources(
        id INTEGER PRIMARY KEY, denomination_id INTEGER, title TEXT, document_type TEXT,
        source_url TEXT, source_authority TEXT, license_status TEXT, active INTEGER,
        permission_ref TEXT, license_review_note TEXT
      );
      INSERT INTO denominations VALUES (1, 'KMC', '기독교대한감리회');
      INSERT INTO doctrine_sources VALUES
        (1, 1, '교리와 장정 2021', 'doctrine_web_reference', 'https://kmc.or.kr/2021', 'OFFICIAL', 'RESTRICTED', 0, '', '원문 복사 금지'),
        (2, 1, '제1편 역사와 교리 1', 'doctrine_web_reference', 'https://kmc.or.kr/2025/1', 'OFFICIAL', 'RESTRICTED', 0, '', '참조 전용'),
        (3, 1, '제2편 헌법', 'constitution_web_reference', 'https://kmc.or.kr/2025/2', 'OFFICIAL', 'RESTRICTED', 0, '', '참조 전용');
    ''')
    con.close()
    result = probe_kmc_reference_headers(db, opener=_Opener(), resolver=lambda *args, **kwargs: [(None, None, None, None, ('8.8.8.8', 0))])
    assert result['body_read'] is False
    assert result['download_performed'] is False
    assert result['results'][0]['status'] == 'checked'
    con = sqlite3.connect(db)
    assert con.execute('SELECT COUNT(*) FROM kmc_reference_check_logs').fetchone()[0] == 3
    assert con.execute('SELECT COUNT(*) FROM kmc_reference_check_logs WHERE body_read=0').fetchone()[0] == 3
    con.close()
    result = compare_kmc_reference_metadata(db)
    assert result['comparison_type'] == 'metadata_inventory'
    assert result['text_compared'] is False
    assert result['download_performed'] is False
    assert result['indexable'] is False
    assert result['editions']['2021']['count'] == 1
    assert result['editions']['2025']['count'] == 2
    assert '제2편 헌법' in result['added_in_2025']


class _Response:
    status = 200
    headers = {'ETag': '"kmc-v1"', 'Last-Modified': 'Sat, 05 Sep 2026 00:00:00 GMT', 'Content-Length': '1234'}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return 'https://kmc.or.kr/reference'

    def read(self, *args):
        raise AssertionError('KMC HEAD probe must not read response body')


class _Opener:
    def open(self, request, timeout):
        assert request.get_method() == 'HEAD'
        return _Response()


def test_kmc_header_probe_never_reads_body(tmp_path):
    db = tmp_path / 'kmc.sqlite3'
    con = sqlite3.connect(db)
    con.executescript('''
      CREATE TABLE denominations(id INTEGER PRIMARY KEY, code TEXT, name_ko TEXT);
      CREATE TABLE doctrine_sources(id INTEGER PRIMARY KEY, denomination_id INTEGER, title TEXT, document_type TEXT, source_url TEXT, source_authority TEXT, license_status TEXT, active INTEGER, permission_ref TEXT, license_review_note TEXT);
      INSERT INTO denominations VALUES (1, 'KMC', '기독교대한감리회');
      INSERT INTO doctrine_sources VALUES (1, 1, '제1편 역사와 교리 1', 'doctrine_web_reference', 'https://kmc.or.kr/reference', 'OFFICIAL', 'RESTRICTED', 0, '', '참조 전용');
    ''')
    con.close()


def test_kmc_metadata_survives_existing_sqlite_backup_restore(tmp_path):
    db = tmp_path / 'source.sqlite3'
    init_db(db)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE IF NOT EXISTS kmc_reference_baselines (source_id TEXT PRIMARY KEY, url TEXT NOT NULL, final_url TEXT NOT NULL DEFAULT '', http_status INTEGER NOT NULL DEFAULT 0, etag TEXT NOT NULL DEFAULT '', last_modified TEXT NOT NULL DEFAULT '', content_length TEXT NOT NULL DEFAULT '', checked_at TEXT NOT NULL, changed INTEGER NOT NULL DEFAULT 0)")
    con.execute("CREATE TABLE IF NOT EXISTS kmc_reference_check_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL, url TEXT NOT NULL, final_url TEXT NOT NULL DEFAULT '', http_status INTEGER NOT NULL DEFAULT 0, etag TEXT NOT NULL DEFAULT '', last_modified TEXT NOT NULL DEFAULT '', content_length TEXT NOT NULL DEFAULT '', checked_at TEXT NOT NULL, changed INTEGER, result_status TEXT NOT NULL, body_read INTEGER NOT NULL DEFAULT 0)")
    con.execute("INSERT INTO kmc_reference_baselines VALUES ('kmc-reference-1','https://kmc.or.kr/x','https://kmc.or.kr/x',200,'','Sat, 05 Sep 2026 00:00:00 GMT','','2026-09-05T00:00:00+00:00',0)")
    con.execute("INSERT INTO kmc_reference_check_logs(source_id,url,checked_at,result_status,body_read) VALUES ('kmc-reference-1','https://kmc.or.kr/x','2026-09-05T00:00:00+00:00','checked',0)")
    con.commit(); con.close()
    backup = create_backup(db, tmp_path / 'backups', '40.9.10')['filename']
    restore_backup(tmp_path / 'backups' / backup, db, tmp_path / 'backups', '40.9.10')
    con = sqlite3.connect(db)
    assert con.execute('SELECT COUNT(*) FROM kmc_reference_baselines').fetchone()[0] == 1
    assert con.execute('SELECT body_read FROM kmc_reference_check_logs').fetchone()[0] == 0
    con.close()
    gate = kmc_reference_review_gate(db)
    assert gate['ready_for_automatic_processing'] is False
    assert gate['automatic_download_allowed'] is False
    assert gate['automatic_indexing_allowed'] is False
