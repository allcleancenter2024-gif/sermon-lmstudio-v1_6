import sqlite3

from app.core import build_research_packet, init_db
from app.kmc_reference import fetch_kmc_reference_sources


def _seed(db):
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO denominations(code,name_ko,created_at,updated_at) VALUES('KMC','기독교대한감리회',datetime('now'),datetime('now'))")
        con.executemany(
            """INSERT INTO doctrine_sources(denomination_id,title,document_type,source_url,source_authority,license_status,active,created_at,updated_at)
               VALUES(1,?,?,?,?,?,0,datetime('now'),datetime('now'))""",
            [('역사와 교리 1','doctrine_web_reference','https://kmc.or.kr/a','OFFICIAL_DENOMINATIONAL','RESTRICTED'),
             ('헌법','constitution_web_reference','https://kmc.or.kr/b','OFFICIAL_DENOMINATIONAL','RESTRICTED')])


def test_kmc_references_are_metadata_only(tmp_path):
    db = tmp_path / 'bible.db'; init_db(db); _seed(db)
    refs = fetch_kmc_reference_sources(db)
    assert len(refs) == 2
    assert all(x['reference_only'] and not x['indexable'] and not x['text'] for x in refs)
    assert all(x['copyright_status'] == 'RESTRICTED' for x in refs)


def test_research_packet_exposes_kmc_references_separately(tmp_path):
    db = tmp_path / 'bible.db'; init_db(db); _seed(db)
    packet = build_research_packet('JHN 3:16', db_path=db, denomination_code='KMC')
    assert len(packet['reference_sources']) == 2
    assert packet['doctrine_sources'] == []
    assert all(not item['text'] for item in packet['reference_sources'])
