from contextlib import closing
import tempfile
import unittest
import zipfile
import json
import sqlite3
from unittest.mock import patch
from pathlib import Path

from app.core import (
    SUPPORTED_SERMON_MINUTES,
    DEFAULT_SERMON_MINUTES,
    build_passage_study, passage_context,
    sermon_time_plan, build_outline_prompt, validate_sermon_outline, outline_references,
    add_doctrine_chunk, add_original_note, add_passage, build_doctrine_index, build_resize_prompt,
    build_sermon_prompt, compare_reference, compare_sermon_versions, build_rag_index, db_stats,
    doctrine_search, estimate_minutes, hybrid_search, import_items, list_sermons, original_notes,
    rag_stats, recommend_related, register_translation_license, save_sermon, search_passages,
    semantic_search, sermon_versions, translation_licenses, validate_quotes,
    create_generation_audit, audit_for_version, add_sermon_review, sermon_review_state,
    analyze_citations, reaudit_sermon_version, lock_sermon_version,
    generate_revision_suggestions, apply_revision_suggestions, revision_suggestions,
    get_reading_cpm, set_reading_cpm, calibrate_reading_cpm, update_project_meta, get_project_meta, project_dashboard,
    sermon_workflow_status,
    normalize_lmstudio_url, set_lmstudio_url, get_lmstudio_url, LMStudioClient,
)
from app.exporters import dashboard_html, pdf_document_html, write_docx, write_final_package


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        add_passage("TEST", "ko", "테스트 1:1", "두려워하지 말라는 시험용 본문입니다.", "test-only", self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_search(self):
        rows = search_passages("테스트 1:1", db_path=self.db)
        self.assertEqual(rows[0]["translation"], "TEST")

    def test_duration(self):
        self.assertEqual(estimate_minutes("가" * 660), 2.0)

    def test_v16_lmstudio_url_is_local_and_persistent(self):
        self.assertEqual(normalize_lmstudio_url("http://127.0.0.1:12345"), "http://127.0.0.1:12345/v1")
        self.assertEqual(normalize_lmstudio_url("http://localhost:5678/v1/"), "http://localhost:5678/v1")
        with self.assertRaises(ValueError):
            normalize_lmstudio_url("https://example.com/v1")
        stored = set_lmstudio_url("http://127.0.0.1:4321", self.db)
        self.assertEqual(stored, "http://127.0.0.1:4321/v1")
        self.assertEqual(get_lmstudio_url(self.db), stored)
        self.assertEqual(LMStudioClient(base_url="http://127.0.0.1:4321").base_url, stored)

    def test_v408_legacy_default_port_is_migrated_to_12345(self):
        set_lmstudio_url("http://127.0.0.1:1234/v1", self.db)
        self.assertEqual(get_lmstudio_url(self.db), "http://127.0.0.1:12345/v1")
        with closing(sqlite3.connect(self.db)) as con:
            value = json.loads(con.execute("SELECT value_json FROM app_settings WHERE key='lmstudio_url'").fetchone()[0])
        self.assertEqual(value, "http://127.0.0.1:12345/v1")

    def test_v16_lmstudio_catalog_separates_generation_and_embedding_models(self):
        client = LMStudioClient(base_url="http://127.0.0.1:12345/v1")
        client._request = lambda method, path, payload=None: {"data": [
            {"id": "google/gemma-4-31b-qat"},
            {"id": "text-embedding-nomic-embed-text-v1.5"},
        ]}
        with patch("app.core.loaded_model_ids", return_value=None):
            catalog = client.model_catalog()
        self.assertEqual(catalog["source"], "openai_compatible")
        self.assertEqual(catalog["generation_models"], ["google/gemma-4-31b-qat"])
        self.assertEqual(catalog["embedding_models"], ["text-embedding-nomic-embed-text-v1.5"])

    def test_v408_catalog_filters_downloaded_but_not_loaded_models(self):
        client = LMStudioClient(base_url="http://127.0.0.1:12345/v1")
        client._request = lambda method, path, payload=None: {"data": [
            {"id": "text-embedding-nomic-embed-text-v1.5"},
            {"id": "qwen/qwen3.6-27b"},
            {"id": "google/gemma-4-31b-qat"},
        ]}
        with patch("app.core.loaded_model_ids", return_value={"text-embedding-nomic-embed-text-v1.5", "qwen/qwen3.6-27b"}):
            catalog = client.model_catalog()
        self.assertEqual(catalog["generation_models"], ["qwen/qwen3.6-27b"])
        self.assertEqual(catalog["embedding_models"], ["text-embedding-nomic-embed-text-v1.5"])
        self.assertIn("1개", catalog["warnings"][0])

    def test_v16_lmstudio_models_fall_back_to_native_catalog_without_claiming_loaded(self):
        client = LMStudioClient(base_url="http://127.0.0.1:12345/v1")
        client._request = lambda method, path, payload=None: {"error": "unexpected endpoint"}
        client._request_url = lambda method, url, payload=None: {"data": [
            {"id": "google/gemma-4-31b-qat"},
            {"id": "text-embedding-nomic-embed-text-v1.5"},
        ]}
        catalog = client.model_catalog()
        self.assertEqual(catalog["source"], "native_model_fallback")
        self.assertFalse(catalog["openai_models_ok"])
        self.assertIn("설치된 모델", catalog["warnings"][0])

    def test_prompt_has_grounding_rule(self):
        rows = search_passages("두려워", db_path=self.db)
        system, user = build_sermon_prompt({"topic": "두려움", "minutes": 20}, rows)
        self.assertIn("실제로 제공된 문장만", system)
        self.assertIn("TEST | 테스트 1:1", user)

    def test_unknown_reference_flag(self):
        rows = search_passages("테스트", db_path=self.db)
        unknown = validate_quotes("테스트 1:1 그리고 다른책 2:3", rows)
        self.assertIn("다른책 2:3", unknown)
        self.assertNotIn("테스트 1:1", unknown)

    def test_bulk_import_and_parallel_compare(self):
        import_items([
            {"translation": "EN", "language": "en", "reference": "테스트 1:1", "text": "Test text"},
            {"translation": "GRC", "language": "grc", "reference": "테스트 1:1", "text": "δοκιμή"},
        ], self.db)
        rows = compare_reference("테스트 1:1", self.db)
        self.assertEqual(len(rows), 3)
        self.assertEqual(db_stats(self.db)["translations"], 3)

    def test_resize_prompt_keeps_grounding(self):
        rows = search_passages("테스트", db_path=self.db)
        system, user = build_resize_prompt("짧은 설교", 20, rows)
        self.assertIn("새로운 성경 인용", system)
        self.assertIn("TEST | 테스트 1:1", user)
        for minutes in (15, 20, 25, 30):
            _, personalized = build_resize_prompt("짧은 설교", minutes, rows, 300)
            self.assertIn("300자/분", personalized)
            self.assertIn(f"{minutes * 300}자", personalized)

    def test_dashboard_escapes_content(self):
        page = dashboard_html(
            sermon="<script>alert(1)</script>",
            meta={"topic": "테스트", "target_minutes": 20, "minutes_estimate": 19.8},
            sources=[],
        )
        self.assertIn("SERMON EVIDENCE DASHBOARD", page)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_local_embedding_rag(self):
        add_passage("TEST", "ko", "테스트 2:1", "평안과 위로에 관한 본문", "test-only", self.db)

        class FakeEmbeddingClient:
            def embeddings(self, model, texts):
                result = []
                for text in texts:
                    if "평안" in text or "위로" in text:
                        result.append([1.0, 0.0])
                    else:
                        result.append([0.0, 1.0])
                return result

        client = FakeEmbeddingClient()
        self.assertEqual(build_rag_index(client, "fake-embed", self.db), 2)
        self.assertEqual(rag_stats(self.db)["indexed"], 2)
        semantic = semantic_search("마음의 평안", client, "fake-embed", 2, self.db)
        self.assertEqual(semantic[0]["reference"], "테스트 2:1")
        hybrid = hybrid_search("마음의 평안", client, "fake-embed", 2, self.db)
        self.assertEqual(hybrid[0]["reference"], "테스트 2:1")

        add_passage("TEST", "ko", "테스트 2:1", "수정된 본문", "test-only", self.db)
        self.assertEqual(rag_stats(self.db)["indexed"], 1)

    def test_original_language_notes_are_grounded(self):
        add_original_note({
            "reference": "테스트 1:1", "language": "he", "lemma": "שָׁלוֹם",
            "transliteration": "shalom", "gloss": "평안", "morphology": "noun",
            "source": "TEST-SOURCE", "license_note": "test-only",
        }, self.db)
        notes = original_notes("테스트 1:1", self.db)
        self.assertEqual(notes[0]["gloss"], "평안")
        rows = search_passages("테스트", db_path=self.db)
        _, user = build_sermon_prompt({"topic": "평안", "minutes": 20}, rows, notes)
        self.assertIn("שָׁלוֹם", user)
        self.assertIn("TEST-SOURCE", user)

    def test_related_passage_recommendation_excludes_base_reference(self):
        add_passage("TEST", "ko", "테스트 2:1", "평안과 위로", "test-only", self.db)
        class FakeEmbeddingClient:
            def embeddings(self, model, texts):
                return [[1.0, 0.0] if ("평안" in t or "위로" in t) else [0.0, 1.0] for t in texts]
        client = FakeEmbeddingClient()
        build_rag_index(client, "fake-embed", self.db)
        related = recommend_related("테스트 1:1", client, "fake-embed", 4, self.db)
        self.assertTrue(all(item["reference"] != "테스트 1:1" for item in related))

    def test_translation_license_can_block_fulltext(self):
        register_translation_license({
            "translation": "RESTRICTED", "license_status": "restricted", "allow_fulltext": False,
            "copyright_holder": "holder", "permission_ref": "", "source_url": "", "notes": "",
        }, self.db)
        self.assertEqual(translation_licenses(self.db)[0]["translation"], "RESTRICTED")
        with self.assertRaises(ValueError):
            add_passage("RESTRICTED", "ko", "테스트 9:9", "저장되면 안 됨", "", self.db)

    def test_doctrine_rag_filters_tradition(self):
        add_doctrine_chunk({"tradition":"장로교","title":"테스트 신앙고백","section":"1","text":"은혜와 믿음","source_url":"official","license_note":"test"}, self.db)
        add_doctrine_chunk({"tradition":"감리교","title":"다른 문서","section":"1","text":"은혜와 믿음","source_url":"official","license_note":"test"}, self.db)
        class FakeEmbeddingClient:
            def embeddings(self, model, texts): return [[1.0, 0.0] for _ in texts]
        client=FakeEmbeddingClient(); self.assertEqual(build_doctrine_index(client,"fake",self.db),2)
        rows=doctrine_search("은혜","장로교",client,"fake",6,self.db)
        self.assertEqual(len(rows),1); self.assertEqual(rows[0]["tradition"],"장로교")

    def test_sermon_version_save_load_and_diff(self):
        first=save_sermon("테스트 설교","첫 원고",{"minutes":20},db_path=self.db)
        second=save_sermon("테스트 설교","수정 원고",{"minutes":20},sermon_id=first["sermon_id"],db_path=self.db)
        self.assertEqual(second["version"],2)
        self.assertEqual(list_sermons(self.db)[0]["latest_version"],2)
        self.assertEqual(sermon_versions(first["sermon_id"],self.db)[0]["content"],"수정 원고")
        diff=compare_sermon_versions(first["sermon_id"],1,2,self.db)
        self.assertIn("-첫 원고",diff); self.assertIn("+수정 원고",diff)

    def test_pdf_layout_uses_local_korean_font_policy(self):
        page=pdf_document_html(sermon="설교",meta={"topic":"테스트"},sources=[])
        self.assertIn("A4 landscape",page)
        self.assertIn("NanumSquare",page)
        dash=dashboard_html(sermon="설교",meta={"topic":"테스트"},sources=[])
        self.assertIn("S-Core Dream",dash)

    def test_v8_citation_and_revision_status_are_in_dashboard_pdf_and_word(self):
        citation = {"mapped_count": 1, "unsupported_count": 1, "mappings": [{"sentence": 1, "text": "테스트 1:1", "references": ["테스트 1:1"]}], "unsupported_claims": [{"sentence": 2, "text": "성경은 이렇게 말합니다.", "reason": "근거 없음"}]}
        meta = {"topic": "V8 출력", "citation_analysis": citation, "review_state": {"state": "locked"}, "revision_parent_version": 1, "applied_suggestion_ids": [7]}
        dash = dashboard_html(sermon="설교", meta=meta, sources=[])
        pdf = pdf_document_html(sermon="설교", meta=meta, sources=[])
        self.assertIn("문장별 성경 근거 연결", dash)
        self.assertIn("목회자 승인 · 최종 잠금본", dash)
        self.assertIn("AI 수정 제안 반영본", dash)
        self.assertIn("확인 필요", pdf)
        self.assertIn("AI 수정: v1 기반", pdf)
        path = Path(self.tmp.name) / "v7.docx"
        write_docx(path, sermon="설교", meta=meta)
        from docx import Document
        text = "\n".join(p.text for p in Document(path).paragraphs)
        self.assertIn("문장별 성경 근거 연결", text)
        self.assertIn("AI 수정 v1 기반", text)

    def test_generation_audit_and_review_state_machine(self):
        rows = search_passages("테스트", db_path=self.db)
        audit = create_generation_audit(
            model="fake-chat", embedding_model="fake-embed", search_mode="하이브리드 RAG",
            target_minutes=20, actual_minutes=20.0, passages=rows, unchecked=[],
            word_notes=[], doctrine_notes=[], db_path=self.db,
        )
        self.assertEqual(audit["status"], "ready_for_review")
        saved = save_sermon("감사 테스트", "테스트 1:1 설교", {"audit_id": audit["id"]}, db_path=self.db)
        self.assertTrue(saved["audit_linked"])
        linked = audit_for_version(saved["sermon_id"], saved["version"], self.db)
        self.assertEqual(linked["id"], audit["id"])
        add_sermon_review(saved["sermon_id"], 1, "검토자", "comment", "근거 확인", self.db)
        add_sermon_review(saved["sermon_id"], 1, "검토자", "approved", "승인", self.db)
        self.assertTrue(sermon_review_state(saved["sermon_id"], 1, self.db)["approved"])
        with self.assertRaises(ValueError):
            add_sermon_review(saved["sermon_id"], 1, "검토자", "changes_requested", "되돌리기", self.db)
        copied = save_sermon("감사 테스트", "복제 원고", {"audit_id": audit["id"], "audit": audit}, sermon_id=saved["sermon_id"], db_path=self.db)
        self.assertFalse(copied["audit_linked"])
        self.assertIsNone(audit_for_version(saved["sermon_id"], 2, self.db))
        self.assertNotIn("audit_id", sermon_versions(saved["sermon_id"], self.db)[0]["metadata"])

    def test_audit_warnings_block_approval(self):
        rows = search_passages("테스트", db_path=self.db)
        audit = create_generation_audit(
            model="fake-chat", embedding_model="", search_mode="문자검색",
            target_minutes=20, actual_minutes=10.0, passages=rows, unchecked=["다른책 2:3"],
            word_notes=[], doctrine_notes=[], db_path=self.db,
        )
        self.assertEqual(audit["status"], "needs_review")
        saved = save_sermon("경고 테스트", "원고", {"audit_id": audit["id"]}, db_path=self.db)
        with self.assertRaises(ValueError):
            add_sermon_review(saved["sermon_id"], 1, "검토자", "approved", "승인 시도", self.db)

    def test_change_request_requires_a_new_version_before_approval(self):
        rows = search_passages("테스트", db_path=self.db)
        audit = create_generation_audit(
            model="fake-chat", embedding_model="", search_mode="문자검색",
            target_minutes=20, actual_minutes=20.0, passages=rows, unchecked=[],
            word_notes=[], doctrine_notes=[], db_path=self.db,
        )
        saved = save_sermon("변경 요청", "원고", {"audit_id": audit["id"]}, db_path=self.db)
        add_sermon_review(saved["sermon_id"], 1, "검토자", "changes_requested", "적용 부분을 보완하세요.", self.db)
        with self.assertRaises(ValueError):
            add_sermon_review(saved["sermon_id"], 1, "검토자", "approved", "같은 버전 승인", self.db)

    def test_sentence_citation_mapping_flags_evidence_claim_without_reference(self):
        rows = search_passages("테스트", db_path=self.db)
        analysis = analyze_citations(
            "성경은 테스트 1:1에서 두려움을 다룹니다.\n성경은 분명 이렇게 말합니다.\n오늘 우리는 용기를 냅니다.",
            rows,
        )
        self.assertEqual(analysis["mapped_count"], 1)
        self.assertEqual(analysis["unsupported_count"], 1)
        self.assertEqual(analysis["mappings"][0]["references"], ["테스트 1:1"])

    def test_reaudit_saved_version_uses_stored_evidence(self):
        rows = search_passages("테스트", db_path=self.db)
        sermon = "성경은 테스트 1:1에서 두려움을 다룹니다."
        saved = save_sermon("재감사", sermon, {
            "sources": rows, "target_minutes": 1, "model": "fake", "search_mode": "문자검색",
            "original_notes": [], "doctrine_sources": [],
        }, db_path=self.db)
        audit = reaudit_sermon_version(saved["sermon_id"], 1, self.db)
        self.assertEqual(audit["citation_analysis"]["mapped_count"], 1)
        self.assertEqual(audit["citation_analysis"]["unsupported_count"], 0)
        self.assertEqual(audit_for_version(saved["sermon_id"], 1, self.db)["id"], audit["id"])

    def test_final_lock_requires_approval_and_freezes_review(self):
        rows = search_passages("테스트", db_path=self.db)
        citations = analyze_citations("성경은 테스트 1:1에서 두려움을 다룹니다.", rows)
        audit = create_generation_audit(
            model="fake", embedding_model="", search_mode="문자검색", target_minutes=20, actual_minutes=20,
            passages=rows, unchecked=[], word_notes=[], doctrine_notes=[], citation_analysis=citations, db_path=self.db,
        )
        saved = save_sermon("최종 잠금", "성경은 테스트 1:1에서 두려움을 다룹니다.", {"audit_id": audit["id"]}, db_path=self.db)
        with self.assertRaises(ValueError):
            lock_sermon_version(saved["sermon_id"], 1, "담임목사", self.db)
        add_sermon_review(saved["sermon_id"], 1, "담임목사", "approved", "최종 확인", self.db)
        with self.assertRaises(ValueError):
            reaudit_sermon_version(saved["sermon_id"], 1, self.db)
        lock = lock_sermon_version(saved["sermon_id"], 1, "담임목사", self.db)
        state = sermon_review_state(saved["sermon_id"], 1, self.db)
        self.assertEqual(state["state"], "locked")
        self.assertTrue(state["lock"]["integrity_ok"])
        self.assertEqual(lock["audit_id"], audit["id"])
        with self.assertRaises(ValueError):
            add_sermon_review(saved["sermon_id"], 1, "담임목사", "comment", "잠금 후 댓글", self.db)
        with self.assertRaises(ValueError):
            reaudit_sermon_version(saved["sermon_id"], 1, self.db)

    def test_v8_grounded_suggestion_creates_new_reaudited_version(self):
        rows = search_passages("테스트", db_path=self.db)
        opening = "성경은 우리에게 두려워하지 말라고 말합니다."
        filler = " 오늘도 은혜 안에서 한 걸음씩 살아갑니다." * 18
        sermon = opening + filler
        citations = analyze_citations(sermon, rows)
        audit = create_generation_audit(
            model="fake", embedding_model="", search_mode="문자검색", target_minutes=1,
            actual_minutes=estimate_minutes(sermon), passages=rows, unchecked=[], word_notes=[], doctrine_notes=[],
            citation_analysis=citations, db_path=self.db,
        )
        saved = save_sermon("V8 수정", sermon, {
            "audit_id": audit["id"], "sources": rows, "target_minutes": 1, "model": "fake",
            "search_mode": "문자검색", "original_notes": [], "doctrine_sources": [],
        }, db_path=self.db)

        class InvalidClient:
            def chat(self, model, system, user, temperature=0.1):
                return '{"suggestions":[{"sentence":1,"proposed_text":"성경은 가짜 9:9에서 말합니다.","references":["가짜 9:9"],"rationale":"가짜"}]}'

        invalid = generate_revision_suggestions(saved["sermon_id"], 1, InvalidClient(), "fake", self.db)
        self.assertEqual(invalid["items"], [])
        self.assertEqual(invalid["invalid_count"], 1)

        class GoodClient:
            def chat(self, model, system, user, temperature=0.1):
                return '{"suggestions":[{"sentence":1,"proposed_text":"성경은 테스트 1:1에서 두려움을 다룹니다.","references":["테스트 1:1"],"rationale":"등록된 근거를 같은 문장에 연결"}]}'

        generated = generate_revision_suggestions(saved["sermon_id"], 1, GoodClient(), "fake", self.db)
        self.assertEqual(len(generated["items"]), 1)
        suggestion_id = generated["items"][0]["id"]
        invalid_again = generate_revision_suggestions(saved["sermon_id"], 1, InvalidClient(), "fake", self.db)
        self.assertEqual(invalid_again["items"], [])
        self.assertEqual(revision_suggestions(saved["sermon_id"], 1, self.db)[-1]["status"], "pending")
        applied = apply_revision_suggestions(saved["sermon_id"], 1, [suggestion_id], self.db)
        self.assertEqual(applied["version"], 2)
        self.assertIn("테스트 1:1", applied["content"])
        self.assertEqual(applied["citation_analysis"]["unsupported_count"], 0)
        stored = revision_suggestions(saved["sermon_id"], 1, self.db)
        self.assertEqual(stored[-1]["status"], "applied")
        self.assertEqual(stored[-1]["applied_version"], 2)

    def test_v9_reading_speed_calibration_and_project_dashboard(self):
        self.assertEqual(get_reading_cpm(self.db), 330)
        self.assertEqual(set_reading_cpm(300, self.db), 300)
        self.assertEqual(calibrate_reading_cpm("가" * 300, 60, self.db), 300)
        saved = save_sermon("V9 프로젝트", "가" * 6000, {"target_minutes": 20, "reading_cpm": 300}, db_path=self.db)
        project = update_project_meta(saved["sermon_id"], service_date="2026-08-16", series_name="믿음 시리즈", preacher="담임목사", notes="주일예배", db_path=self.db)
        self.assertEqual(project["series_name"], "믿음 시리즈")
        self.assertEqual(get_project_meta(saved["sermon_id"], self.db)["service_date"], "2026-08-16")
        dashboard = project_dashboard(self.db)
        self.assertEqual(dashboard["summary"]["total"], 1)
        self.assertEqual(dashboard["projects"][0]["minutes_estimate"], 20.0)
        self.assertEqual(dashboard["projects"][0]["reading_cpm"], 300)

    def test_v9_final_package_contains_manifest_dashboard_word_and_markdown(self):
        output = Path(self.tmp.name) / "final.zip"
        meta = {
            "topic": "최종 설교", "target_minutes": 20, "minutes_estimate": 20.0, "reading_cpm": 300,
            "audit": {"status": "ready_for_review"}, "review_state": {"state": "locked", "lock": {"integrity_ok": True}},
            "citation_analysis": {"mapped_count": 0, "unsupported_count": 0, "mappings": [], "unsupported_claims": []},
            "study_note": {"note_markdown": "# 본문 연구 노트\n등록 근거"},
            "outline": {"title": "검증된 설교 구조", "time_plan": {"target_minutes": 20}},
        }
        manifest = write_final_package(output, sermon="최종 설교 원고", meta=meta, sources=[], project={"service_date": "2026-08-16", "preacher": "담임목사"})
        self.assertEqual(manifest["review_state"], "locked")
        self.assertEqual(manifest["format"], "sermon-lmstudio-final-package-v40")
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            self.assertTrue({"sermon.md", "dashboard.html", "sermon.docx", "study_note.md", "sermon_outline.json", "manifest.json"}.issubset(names))

    def test_v10_fifteen_minutes_is_an_official_api_duration(self):
        self.assertEqual(SUPPORTED_SERMON_MINUTES, (15, 20, 25, 30))
        with self.assertRaises(ValueError):
            sermon_time_plan(40)
        self.assertEqual(DEFAULT_SERMON_MINUTES, 15)
        rows = search_passages("테스트", db_path=self.db)
        _, prompt = build_sermon_prompt({"topic": "평안", "minutes": 15, "reading_cpm": 300}, rows)
        self.assertIn("15분", prompt)
        self.assertIn("4500자", prompt)
        _, default_prompt = build_sermon_prompt({"topic": "평안", "reading_cpm": 300}, rows)
        self.assertIn("15분", default_prompt)

    def test_v10_workflow_is_derived_from_audit_review_and_lock(self):
        rows = search_passages("테스트", db_path=self.db)
        audit = create_generation_audit(
            model="fake", embedding_model="", search_mode="문자검색",
            target_minutes=15, actual_minutes=15.0, passages=rows, unchecked=[],
            word_notes=[], doctrine_notes=[], db_path=self.db,
        )
        meta = {
            "topic": "V10 Wizard", "main_reference": "테스트 1:1", "target_minutes": 15,
            "reading_cpm": 300, "sources": rows, "audit_id": audit["id"],
        }
        saved = save_sermon("V10 Wizard", "테스트 1:1 설교", meta, db_path=self.db)
        status = sermon_workflow_status(saved["sermon_id"], 1, self.db)
        self.assertEqual(status["steps"][1]["status"], "completed")
        self.assertEqual(status["steps"][4]["status"], "completed")
        self.assertEqual(status["next_step"], "languages")

        add_sermon_review(saved["sermon_id"], 1, "검토자", "approved", "승인", self.db)
        lock_sermon_version(saved["sermon_id"], 1, "검토자", self.db)
        locked = sermon_workflow_status(saved["sermon_id"], 1, self.db)
        self.assertEqual(locked["steps"][5]["status"], "completed")
        self.assertEqual(locked["steps"][6]["status"], "completed")
        self.assertTrue(locked["locked"])

    def test_v11_passage_study_uses_registered_translation_original_and_context(self):
        add_passage("TEST-EN", "en", "테스트 1:1", "Do not fear in this test passage.", "test-only", self.db)
        add_passage("TEST", "ko", "테스트 1:2", "시험용 다음 절 문맥입니다.", "test-only", self.db)
        add_original_note({
            "reference": "테스트 1:1", "language": "he", "lemma": "ירא", "transliteration": "yare",
            "gloss": "두려워하다", "morphology": "동사", "source": "test lexicon", "license_note": "test-only",
        }, self.db)
        context = passage_context("테스트 1:1", self.db)
        self.assertEqual(context[0]["reference"], "테스트 1:2")
        study = build_passage_study("테스트 1:1", related=[{
            "reference": "테스트 1:2", "translation": "TEST", "text": "관련 절", "semantic_score": 0.91,
        }], db_path=self.db)
        self.assertEqual(study["counts"], {"translations": 2, "original_notes": 1, "context": 1, "related": 1})
        self.assertFalse(study["warnings"])
        self.assertIn("TEST-EN", study["note_markdown"])
        self.assertIn("ירא", study["note_markdown"])
        self.assertIn("앞뒤 절 문맥", study["note_markdown"])
        saved = save_sermon("V11 연구노트", "테스트 1:1 설교", {
            "sources": [study["translations"][0]], "study_note": {
                "reference": study["reference"], "counts": study["counts"], "note_markdown": study["note_markdown"],
            },
        }, db_path=self.db)
        workflow = sermon_workflow_status(saved["sermon_id"], 1, self.db)
        self.assertEqual(workflow["steps"][2]["status"], "completed")

    def test_v12_time_plan_exactly_matches_every_supported_duration(self):
        for minutes in SUPPORTED_SERMON_MINUTES:
            plan = sermon_time_plan(minutes, 300)
            self.assertEqual(sum(x["minutes"] for x in plan["sections"]), minutes)
            self.assertEqual(sum(x["target_chars"] for x in plan["sections"]), minutes * 300)
            self.assertEqual(plan["target_chars"], minutes * 300)
        fifteen = sermon_time_plan(15, 300)
        self.assertEqual(fifteen["target_minutes"], 15)
        self.assertEqual(fifteen["target_chars"], 4500)
        with self.assertRaises(ValueError):
            sermon_time_plan(18, 300)

    def test_v12_outline_rejects_unregistered_references_and_enters_prompt(self):
        rows = search_passages("테스트 1:1", db_path=self.db)
        study = build_passage_study("테스트 1:1", db_path=self.db)
        plan = sermon_time_plan(15, 300)
        _, outline_prompt = build_outline_prompt({"topic": "믿음", "main_reference": "테스트 1:1"}, study, plan)
        self.assertIn("테스트 1:1", outline_prompt)
        self.assertIn('"target_minutes": 15', outline_prompt)
        outline = {
            "title": "두려움보다 큰 믿음", "core_message": "하나님을 신뢰합니다.",
            "points": [
                {"title": f"대지 {i}", "reference": "테스트 1:1", "explanation": "본문 설명", "application": "삶의 적용", "illustration_direction": "일상의 선택"}
                for i in range(1, 4)
            ],
            "gospel_connection": "복음 연결", "closing_direction": "결론과 기도",
        }
        clean = validate_sermon_outline(outline, rows)
        self.assertEqual(outline_references(clean), ["테스트 1:1"])
        _, prompt = build_sermon_prompt({"topic": "믿음", "minutes": 15, "reading_cpm": 300, "outline": clean}, rows)
        self.assertIn("검증된 설교 구조", prompt)
        self.assertIn("두려움보다 큰 믿음", prompt)
        self.assertIn('"target_minutes": 15', prompt)
        bad = json.loads(json.dumps(outline, ensure_ascii=False))
        bad["points"][0]["reference"] = "없는책 9:9"
        with self.assertRaises(ValueError):
            validate_sermon_outline(bad, rows)


if __name__ == "__main__":
    unittest.main()
