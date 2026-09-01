import tempfile
import unittest
from pathlib import Path

from app.core import (
    add_doctrine_chunk,
    add_original_note,
    add_passage,
    add_sermon_review,
    analyze_citations,
    audit_for_version,
    build_doctrine_index,
    build_rag_index,
    build_sermon_prompt,
    create_generation_audit,
    doctrine_search,
    estimate_minutes,
    hybrid_search,
    lock_sermon_version,
    original_notes,
    save_sermon,
    sermon_review_state,
    validate_quotes,
)


class FakeLMStudioClient:
    """LM Studio의 chat/embeddings 계약만 흉내 내는 오프라인 통합테스트 대역."""

    def models(self):
        return ["fake-chat"]

    def embeddings(self, model, texts):
        return [[1.0, 0.25] for _ in texts]

    def chat(self, model, system, user, temperature=0.35):
        header = "# 두려움 속에서도 함께하시는 하나님\n## 중심본문\n테스트 1:1\n"
        paragraph = "하나님이 함께하신다는 약속을 붙들고 오늘의 두려움을 정직하게 바라봅니다. 믿음은 현실을 외면하는 힘이 아니라 은혜 안에서 한 걸음 순종하게 하는 힘입니다. "
        body = header
        while estimate_minutes(body) < 19.9:
            body += paragraph
        return body + "\n\n목회자 검토 전 초안입니다."


class V7EndToEndTests(unittest.TestCase):
    def test_rag_generation_audit_save_and_pastor_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "e2e.db"
            add_passage("TEST", "ko", "테스트 1:1", "두려워하지 말라 내가 너와 함께한다는 시험용 본문", "test-only", db)
            add_passage("TEST", "ko", "테스트 1:2", "평안과 소망에 관한 시험용 관련 본문", "test-only", db)
            add_original_note({
                "reference": "테스트 1:1", "language": "he", "lemma": "שָׁלוֹם",
                "transliteration": "shalom", "gloss": "평안", "morphology": "noun",
                "source": "TEST-LEXICON", "license_note": "test-only",
            }, db)
            add_doctrine_chunk({
                "tradition": "초교파 복음주의", "title": "테스트 신앙고백", "section": "1",
                "text": "은혜와 믿음에 관한 테스트 문장", "source_url": "https://example.invalid/confession",
                "license_note": "test-only",
            }, db)

            lm = FakeLMStudioClient()
            build_rag_index(lm, "fake-embed", db)
            build_doctrine_index(lm, "fake-embed", db)
            passages = hybrid_search("테스트 1:1 두려움", lm, "fake-embed", 8, db)
            words = original_notes("테스트 1:1", db)
            doctrine = doctrine_search("은혜", "초교파 복음주의", lm, "fake-embed", 4, db)
            payload = {"topic": "두려움", "main_reference": "테스트 1:1", "minutes": 20, "tradition": "초교파 복음주의"}
            system, user = build_sermon_prompt(payload, passages, words, doctrine)
            sermon = lm.chat("fake-chat", system, user)
            minutes = estimate_minutes(sermon)
            unchecked = validate_quotes(sermon, passages)
            citations = analyze_citations(sermon, passages)

            self.assertGreaterEqual(minutes, 19.8)
            self.assertLessEqual(minutes, 20.3)
            self.assertEqual(unchecked, [])
            self.assertGreaterEqual(citations["mapped_count"], 1)
            self.assertEqual(citations["unsupported_count"], 0)

            audit = create_generation_audit(
                model="fake-chat", embedding_model="fake-embed", search_mode="하이브리드 RAG",
                target_minutes=20, actual_minutes=minutes, passages=passages, unchecked=unchecked,
                word_notes=words, doctrine_notes=doctrine, citation_analysis=citations, db_path=db,
            )
            self.assertEqual(audit["status"], "ready_for_review")

            saved = save_sermon("두려움", sermon, {"audit_id": audit["id"], "audit": audit}, db_path=db)
            self.assertEqual(audit_for_version(saved["sermon_id"], 1, db)["id"], audit["id"])
            add_sermon_review(saved["sermon_id"], 1, "담임목사", "comment", "근거 확인 완료", db)
            add_sermon_review(saved["sermon_id"], 1, "담임목사", "approved", "설교 준비용으로 승인", db)
            lock_sermon_version(saved["sermon_id"], 1, "담임목사", db)
            state = sermon_review_state(saved["sermon_id"], 1, db)
            self.assertTrue(state["approved"])
            self.assertEqual(state["state"], "locked")
            self.assertTrue(state["lock"]["integrity_ok"])


if __name__ == "__main__":
    unittest.main()
