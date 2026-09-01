import json
import unittest
from unittest.mock import Mock, patch

from app.core import LMStudioClient
from app.importers import convert_lexicon_source
from app.main import PreflightRequest, SermonOutlineRequest, create_outline, preflight_check


class V34RuntimeConsistencyTests(unittest.TestCase):
    def test_lexicon_xml_explains_correct_oshb_import_route(self):
        with self.assertRaisesRegex(ValueError, "원어 근거 파일 일괄 가져오기"):
            convert_lexicon_source("<osis><osisText/></osis>", "auto")

    def test_generation_probe_uses_real_chat_endpoint_with_one_token(self):
        client = LMStudioClient("http://127.0.0.1:12345/v1")
        with patch.object(client, "_request", return_value={"choices": [{"message": {"content": "O"}}]}) as request:
            client.probe_generation("ready-model")
        method, path, payload = request.call_args.args
        self.assertEqual((method, path), ("POST", "/chat/completions"))
        self.assertEqual(payload["model"], "ready-model")
        self.assertEqual(payload["max_tokens"], 1)

    def test_generation_probe_retries_one_transient_disconnect_after_ready_check(self):
        client = LMStudioClient("http://127.0.0.1:12345/v1")
        transient = ConnectionError("LM Studio 실제 추론 연결이 끊겼습니다: test")
        model_list = {"data": [{"id": "ready-model"}]}
        success = {"choices": [{"message": {"content": "O"}}]}
        with patch("app.core.time.sleep"), patch.object(client, "_request", side_effect=[transient, model_list, success]) as request:
            client.probe_generation("ready-model")
        self.assertEqual(request.call_count, 3)

    def test_generation_probe_does_not_retry_non_transport_error(self):
        client = LMStudioClient("http://127.0.0.1:12345/v1")
        with patch.object(client, "_request", side_effect=ConnectionError("LM Studio API HTTP 400: bad")) as request:
            with self.assertRaisesRegex(ConnectionError, "HTTP 400"):
                client.probe_generation("ready-model")
        self.assertEqual(request.call_count, 1)

    def test_preflight_fails_when_model_list_works_but_inference_is_disconnected(self):
        client = Mock()
        client.model_catalog.return_value = {
            "source": "openai_compatible", "generation_models": ["ready-model"], "embedding_models": []
        }
        client.probe_generation.side_effect = ConnectionError("실제 추론 연결 실패")
        with (
            patch("app.main.LMStudioClient", return_value=client),
            patch("app.main.db_stats", return_value={"passages": 0}),
            patch("app.main.rag_stats", return_value={"models": [], "doctrine_models": []}),
        ):
            result = preflight_check(PreflightRequest(topic="믿음", model="ready-model", use_rag=False))
        lm = next(item for item in result["steps"] if item["key"] == "lmstudio")
        self.assertEqual(lm["state"], "fail")
        self.assertIn("실제 추론 연결 실패", lm["detail"])

    def test_outline_uses_shared_research_packet_readiness_not_separate_empty_study_check(self):
        packet = {
            "readiness": {"generation_ready": True},
            "missing_main_references": [],
            "study": {"translations": [], "context": [], "original_notes": [], "counts": {}},
            "bible_sources": [
                {"translation": "WEB", "language": "en", "reference": "MAT 14:27", "text": "Take courage.", "license_note": "PD"}
            ],
        }
        outline = {
            "title": "주님을 바라보는 믿음",
            "core_message": "두려움 속에서도 주님을 신뢰합니다.",
            "points": [
                {"title": "담대하라", "reference": "MAT 14:27", "explanation": "설명", "application": "적용", "illustration_direction": "예화"},
                {"title": "주님을 보라", "reference": "MAT 14:27", "explanation": "설명", "application": "적용", "illustration_direction": "예화"},
                {"title": "믿음으로 서라", "reference": "MAT 14:27", "explanation": "설명", "application": "적용", "illustration_direction": "예화"},
            ],
            "gospel_connection": "복음",
            "closing_direction": "결론",
        }
        client = Mock()
        client.chat.return_value = json.dumps(outline, ensure_ascii=False)
        with (
            patch("app.main.build_research_packet", return_value=packet),
            patch("app.main.LMStudioClient", return_value=client),
            patch("app.main._select_generation_model", return_value=("ready-model", {})),
        ):
            result = create_outline(
                SermonOutlineRequest(topic="믿음", main_reference="Matt 14:27", model="ready-model", minutes=15)
            )
        self.assertEqual(result["reference"], "MAT 14:27")
        self.assertEqual(len(result["outline"]["points"]), 3)


if __name__ == "__main__":
    unittest.main()
