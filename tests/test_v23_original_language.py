from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

import app.main as main
from app.core import add_original_note, add_passage, build_passage_study, compare_reference, import_original_notes, original_notes, validate_sermon_outline
from app.importers import convert_original_note_source
from app.main import OriginalNoteRequest
from app.references import expand_reference, normalize_reference


class V23ReferenceRangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "bible.db"
        for verse in range(26, 33):
            add_passage("WEB", "en", f"MAT 14:{verse}", f"Matthew verse {verse}", "Public Domain", self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_matt_alias_tilde_range_expands_to_usfm_mat(self):
        self.assertEqual(normalize_reference("MATT 14:27~31"), "MAT 14:27-31")
        self.assertEqual(expand_reference("Matthew 14:27–31"), [f"MAT 14:{v}" for v in range(27, 32)])

    def test_range_finds_each_registered_passage_and_adjacent_context(self):
        study = build_passage_study("MATT 14:27~31", db_path=self.db)
        self.assertEqual([x["reference"] for x in study["translations"]], [f"MAT 14:{v}" for v in range(27, 32)])
        self.assertEqual([x["reference"] for x in study["context"]], ["MAT 14:26", "MAT 14:32"])

    def test_range_collects_original_notes_saved_per_verse(self):
        add_original_note({"reference":"MAT 14:27","language":"grc","lemma":"θαρσέω","gloss":"담대하다"}, self.db)
        add_original_note({"reference":"MAT 14:31","language":"grc","lemma":"διστάζω","gloss":"의심하다"}, self.db)
        notes = original_notes("MATT 14:27~31", self.db)
        self.assertEqual([(x["reference"], x["lemma"]) for x in notes], [("MAT 14:27", "θαρσέω"), ("MAT 14:31", "διστάζω")])

    def test_outline_range_alias_is_allowed_when_every_verse_is_registered(self):
        allowed = compare_reference("MAT 14:27-31", self.db)
        parsed = {
            "title":"물 위를 걸으시는 예수님", "core_message":"믿음으로 주님을 바라봅니다.",
            "points":[
                {"title":"담대하라","reference":"MATT 14:27-28","explanation":"설명","application":"적용","illustration_direction":"방향"},
                {"title":"주님을 보라","reference":"MAT 14:29-30","explanation":"설명","application":"적용","illustration_direction":"방향"},
                {"title":"붙드시는 주님","reference":"MAT 14:31","explanation":"설명","application":"적용","illustration_direction":"방향"},
            ],
            "gospel_connection":"복음", "closing_direction":"결론",
        }
        result = validate_sermon_outline(parsed, allowed)
        self.assertEqual(result["points"][0]["reference"], "MAT 14:27-28")

    def test_cross_chapter_range_is_rejected_explicitly(self):
        with self.assertRaisesRegex(ValueError, "같은 장"):
            expand_reference("MAT 14:31-15:2")

    def test_original_csv_import_normalizes_alias_and_fields(self):
        source = "reference,language,lemma,transliteration,gloss,morphology\nMATT 14:27,grc,θαρσέω,tharseo,담대하다,V-PAM-2P\n"
        resolved, items = convert_original_note_source(source, "auto")
        self.assertEqual(resolved, "csv")
        self.assertEqual(items[0]["reference"], "MAT 14:27")
        self.assertEqual(items[0]["lemma"], "θαρσέω")

    def test_original_import_rejects_range_rows(self):
        source = '[{"reference":"MAT 14:27-31","language":"grc","lemma":"θαρσέω"}]'
        with self.assertRaisesRegex(ValueError, "한 절"):
            convert_original_note_source(source, "json")

    def test_original_bulk_import_is_idempotent_and_records_license(self):
        items = [{"reference":"MATT 14:27","language":"grc","lemma":"θαρσέω","gloss":"담대하다"}]
        first = import_original_notes(items, "사용자가 확인한 형태론 자료", "사용조건 확인", self.db)
        second = import_original_notes(items, "사용자가 확인한 형태론 자료", "사용조건 확인", self.db)
        self.assertEqual(first, {"imported": 1, "skipped_existing": 0})
        self.assertEqual(second, {"imported": 0, "skipped_existing": 1})
        note = original_notes("MAT 14:27", self.db)[0]
        self.assertEqual(note["source"], "사용자가 확인한 형태론 자료")
        self.assertEqual(note["license_note"], "사용조건 확인")

    def test_manual_original_note_api_rejects_range_reference(self):
        data = OriginalNoteRequest(reference="MATT 14:27~31", language="grc", lemma="θαρσέω")
        with self.assertRaises(HTTPException) as raised:
            main.create_original_note(data)
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("한 절", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
