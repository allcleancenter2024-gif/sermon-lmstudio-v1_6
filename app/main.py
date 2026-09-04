from __future__ import annotations

from datetime import datetime
import os
import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app.constants import RECOMMENDED_GENERATION_MODELS, recommended_generation_model
from app.version import APP_VERSION

from app.core import (
    DB_PATH,
    SUPPORTED_SERMON_MINUTES,
    DEFAULT_SERMON_MINUTES,
    LMStudioClient,
    add_passage,
    add_original_note,
    import_original_notes,
    import_original_note_batches,
    import_original_lexicon,
    original_lexicon_stats,
    add_doctrine_chunk,
    build_rag_index,
    build_doctrine_index,
    build_resize_prompt,
    build_sermon_prompt,
    build_passage_study,
    build_research_packet,
    build_social_context_policy,
    build_outline_prompt,
    compact_outline_study,
    validate_sermon_outline,
    sermon_time_plan,
    outline_references,
    _parse_json_response,
    compare_reference,
    bible_database_dashboard,
    bible_database_integrity,
    delete_bible_translation,
    db_stats,
    doctrine_search,
    estimate_minutes,
    init_db,
    import_items,
    hybrid_search,
    original_notes,
    original_language_coverage,
    rag_stats,
    recommend_related,
    register_translation_license,
    save_sermon,
    list_sermons,
    sermon_versions,
    translation_licenses,
    compare_sermon_versions,
    analyze_citations,
    build_post_generation_quality,
    create_generation_audit,
    get_generation_audit,
    add_sermon_review,
    reaudit_sermon_version,
    lock_sermon_version,
    revision_suggestions,
    generate_revision_suggestions,
    apply_revision_suggestions,
    get_reading_cpm,
    set_reading_cpm,
    calibrate_reading_cpm,
    get_project_meta,
    update_project_meta,
    project_dashboard,
    sermon_workflow_status,
    sermon_review_state,
    search_passages,
    validate_quotes,
    get_lmstudio_url,
    set_lmstudio_url,
)
from app.importers import MAX_ZIP_UPLOAD_BYTES, SUPPORTED_SOURCE_FORMATS, classify_original_language_source, convert_bible_source, convert_original_note_source, convert_lexicon_source, convert_usfm_zip, iter_oshb_zip_original_files
from app.backup import BackupError, create_backup, list_backups, restore_backup
from app.exporters import dashboard_html, pdf_environment_status, sermon_with_media_prompts, write_docx, write_hwpx, write_pdf, write_final_package
from app.exporters_grounding import build_grounding_report_data, render_grounding_html, render_grounding_markdown, safe_report_stem
from app.paths import RESOURCE_ROOT, USER_ROOT, EXPORTS_DIR, BACKUPS_DIR
from app.sblgnt_installer import installer_status, start_install
from app.services.greek_morphology_service import get_greek_tokens, lemma_search, normalized_search
from app.services.textual_apparatus_service import get_apparatus_notes
from app.alignment import align_reference
from app.services.greek_text_service import get_greek_text
from app.services.original_language_dashboard import original_language_dashboard
from app.auth import is_admin, session_user, user_count
from app.doctrine_workflow import fetch_indexable_doctrine_chunks, transition_document
from app.doctrine_rag import search_approved_doctrine
from app.references import expand_reference, normalize_reference, normalize_user_reference, parse_reference, primary_original_language, validate_primary_original_language
from app.notebooklm import (
    create_pack,
    drive_status,
    get_drive_folder,
    import_research_note,
    init_notebooklm_db,
    list_research_notes,
    set_drive_folder,
)
from app.github import github_readiness
from app.project_summary import build_project_summary
from app.services.sermon_service import generate_sermon_workflow
from app.providers.web import WebEvidenceAdapter, HttpJsonWebSearchProvider, build_web_query, should_search_web, web_grounding_enabled
from app.providers.lmstudio import cancel_generation
from app.routers.health import router as health_router
from app.routers.settings import router as settings_router
from app.routers.projects import router as projects_router
from app.routers.doctrine import router as doctrine_router
from app.routers.bible import router as bible_router
from app.routers.exports import router as exports_router
from app.routers.auth import AuthRequest, build_auth_router
from app.lmstudio_control import find_lms_cli, local_api_port, port_is_open, start_local_server


ROOT = RESOURCE_ROOT
EXPORTS = EXPORTS_DIR
init_db()

init_notebooklm_db(DB_PATH)
app = FastAPI(title="성경 근거 설교 작성기 - LM Studio Edition", version=APP_VERSION)
app.include_router(health_router)
app.include_router(settings_router)
app.include_router(projects_router)
app.include_router(doctrine_router)
app.include_router(bible_router)
app.include_router(exports_router)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
AUTH_DB = USER_ROOT / "auth.sqlite3"
user_count(AUTH_DB)  # initialize the separate auth store without touching sermon DB
app.include_router(build_auth_router(AUTH_DB))

PUBLIC_BIBLE_IMPORT_PRESETS = [
    {
        "id": "web",
        "label": "World English Bible (WEB)",
        "translation": "WEB",
        "language": "en",
        "license_note": "Public Domain · 수정본은 WEB 이름 사용 조건을 확인하세요.",
        "source_url": "https://ebible.org/bible/details.php?id=engwebp",
        "kind": "scripture",
    },
    {
        "id": "wlc",
        "label": "Westminster Leningrad Codex (WLC)",
        "translation": "WLC",
        "language": "he",
        "license_note": "Public Domain · Westminster Leningrad Codex text",
        "source_url": "https://hb.openscriptures.org/",
        "kind": "scripture",
    },
    {
        "id": "sblgnt",
        "label": "SBL Greek New Testament (SBLGNT)",
        "translation": "SBLGNT",
        "language": "grc",
        "license_note": "CC BY 4.0 · attribution required",
        "source_url": "https://sblgnt.com/download/",
        "kind": "scripture",
    },
    {
        "id": "licensed_custom",
        "label": "정식 사용 허가를 받은 사용자 자료",
        "translation": "",
        "language": "ko",
        "license_note": "",
        "source_url": "",
        "kind": "licensed_custom",
    },
]


@app.middleware("http")
async def runtime_identity_headers(request, call_next):
    # Runtime identity is intentionally public so the launcher can detect the
    # local server before opening the browser; application data APIs remain protected.
    public = request.url.path in {"/", "/login", "/api/runtime", "/api/auth/status", "/api/auth/login", "/api/auth/register"} or request.url.path.startswith("/static/")
    if not public and session_user(request.cookies.get("sermon_session")) is None:
        return JSONResponse({"detail": "로그인이 필요합니다.", "code": "auth_required"}, status_code=401)
    response = await call_next(request)
    response.headers["X-Sermon-App-Version"] = APP_VERSION
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


class SermonRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=120)
    details: str = Field(default="", max_length=3000)
    main_reference: str = Field(default="", max_length=80)
    audience: str = "전 연령"
    tradition: str = "초교파 복음주의"
    denomination_code: str = Field(default="", max_length=40)
    minutes: Literal[15, 20, 25, 30, 40] = DEFAULT_SERMON_MINUTES
    model: str = ""
    embedding_model: str = ""
    use_rag: bool = True
    reading_cpm: int | None = Field(default=None, ge=180, le=600)
    outline: dict | None = None
    web_grounding: bool = False


class PassageRequest(BaseModel):
    translation: str
    language: str = "ko"
    reference: str
    text: str
    license_note: str = ""


class BulkImportRequest(BaseModel):
    items: list[PassageRequest] = Field(min_length=1, max_length=5000)


class BibleWizardItem(BaseModel):
    reference: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=20000)


class BibleWizardImportRequest(BaseModel):
    preset_id: str = Field(min_length=1, max_length=80)
    translation: str = Field(default="", max_length=150)
    language: str = Field(default="", max_length=20)
    license_note: str = Field(default="", max_length=1000)
    source_url: str = Field(default="", max_length=1000)
    confirmed: bool = False
    items: list[BibleWizardItem] = Field(min_length=1, max_length=5000)


class BibleConvertRequest(BaseModel):
    source_format: Literal["auto", "json", "csv", "tsv", "usfm", "osis", "sblgnt_xml"] = "auto"
    content: str = Field(min_length=1, max_length=52_428_800)


class RagIndexRequest(BaseModel):
    model: str = Field(min_length=1, max_length=300)


class OriginalNoteRequest(BaseModel):
    reference: str = Field(min_length=2, max_length=80)
    language: str = Field(min_length=2, max_length=20)
    lemma: str = Field(min_length=1, max_length=200)
    transliteration: str = Field(default="", max_length=200)
    gloss: str = Field(default="", max_length=500)
    morphology: str = Field(default="", max_length=500)
    source: str = Field(default="", max_length=500)
    license_note: str = Field(default="", max_length=500)


class OriginalNoteConvertRequest(BaseModel):
    source_format: Literal["auto", "json", "csv", "tsv", "morphgnt", "oshb_osis"] = "auto"
    content: str = Field(min_length=1, max_length=52_428_800)


class OriginalNoteBulkRequest(BaseModel):
    source: str = Field(min_length=2, max_length=500)
    license_note: str = Field(min_length=2, max_length=500)
    confirmed: bool = False
    items: list[OriginalNoteRequest] = Field(min_length=1, max_length=5000)


class LexiconEntryRequest(BaseModel):
    language: str = Field(min_length=2, max_length=20)
    lemma: str = Field(min_length=1, max_length=200)
    transliteration: str = Field(default="", max_length=200)
    gloss: str = Field(min_length=1, max_length=5000)


class LexiconConvertRequest(BaseModel):
    source_format: Literal[
        "auto", "json", "csv", "tsv", "xml", "strongs_greek_xml", "hebrew_strongs_xml"
    ] = "auto"
    content: str = Field(min_length=1, max_length=52_428_800)


class OriginalLanguageClassifyRequest(BaseModel):
    content: str = Field(min_length=1, max_length=131_072)
    filename: str = Field(default="", max_length=260)


class LexiconBulkRequest(BaseModel):
    source: str = Field(min_length=2, max_length=500)
    license_note: str = Field(min_length=2, max_length=500)
    confirmed: bool = False
    items: list[LexiconEntryRequest] = Field(min_length=1, max_length=5000)


class DoctrineChunkRequest(BaseModel):
    tradition: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=2, max_length=300)
    section: str = Field(default="", max_length=300)
    text: str = Field(min_length=2, max_length=12000)
    source_url: str = Field(default="", max_length=1000)
    license_note: str = Field(default="", max_length=500)


class TranslationLicenseRequest(BaseModel):
    translation: str = Field(min_length=1, max_length=150)
    copyright_holder: str = Field(default="", max_length=300)
    license_status: str = Field(min_length=2, max_length=80)
    permission_ref: str = Field(default="", max_length=500)
    source_url: str = Field(default="", max_length=1000)
    allow_fulltext: bool = False
    notes: str = Field(default="", max_length=1000)


class SermonSaveRequest(BaseModel):
    topic: str = Field(default="제목 없음", max_length=200)
    content: str = Field(min_length=1)
    metadata: dict = {}
    sermon_id: int | None = None


class SermonReviewRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=3, max_length=30)
    comment: str = Field(default="", max_length=5000)


class SermonLockRequest(BaseModel):
    locked_by: str = Field(min_length=1, max_length=100)


class RevisionSuggestionRequest(BaseModel):
    model: str = Field(default="", max_length=300)


class RevisionApplyRequest(BaseModel):
    suggestion_ids: list[int] = Field(min_length=1, max_length=20)


class ReadingSpeedRequest(BaseModel):
    chars_per_minute: int = Field(ge=180, le=600)


class LMStudioSettingsRequest(BaseModel):
    base_url: str = Field(default="http://127.0.0.1:12345/v1", min_length=10, max_length=300)


class LMStudioRecoveryRequest(BaseModel):
    model: str = Field(default="", max_length=300)


class ReadingCalibrationRequest(BaseModel):
    text: str = Field(min_length=80, max_length=10000)
    seconds: float = Field(ge=15, le=3600)


class ProjectMetaRequest(BaseModel):
    service_date: str = Field(default="", max_length=20)
    series_name: str = Field(default="", max_length=200)
    preacher: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=3000)


class SermonOutlineRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=120)
    details: str = Field(default="", max_length=3000)
    main_reference: str = Field(min_length=2, max_length=80)
    audience: str = Field(default="전 연령", max_length=80)
    tradition: str = Field(default="초교파 복음주의", max_length=100)
    minutes: Literal[15, 20, 25, 30, 40] = DEFAULT_SERMON_MINUTES
    model: str = Field(default="", max_length=300)
    reading_cpm: int | None = Field(default=None, ge=180, le=600)


class ResearchPacketRequest(BaseModel):
    topic: str = Field(default="", max_length=120)
    details: str = Field(default="", max_length=3000)
    main_reference: str = Field(min_length=2, max_length=80)
    tradition: str = Field(default="초교파 복음주의", max_length=100)
    denomination_code: str = Field(default="", max_length=40)
    embedding_model: str = Field(default="", max_length=300)
    use_rag: bool = True


class PreflightRequest(BaseModel):
    topic: str = Field(default="", max_length=120)
    details: str = Field(default="", max_length=3000)
    main_reference: str = Field(default="", max_length=80)
    tradition: str = Field(default="초교파 복음주의", max_length=100)
    minutes: Literal[15, 20, 25, 30, 40] = DEFAULT_SERMON_MINUTES
    model: str = Field(default="", max_length=300)
    embedding_model: str = Field(default="", max_length=300)
    use_rag: bool = True
    reading_cpm: int = Field(default=330, ge=180, le=600)


class NotebookPackRequest(BaseModel):
    topic: str = Field(default="", max_length=120)
    main_reference: str = Field(min_length=2, max_length=80)
    tradition: str = Field(default="초교파 복음주의", max_length=100)
    minutes: Literal[15, 20, 25, 30, 40] = DEFAULT_SERMON_MINUTES
    sync_to_drive: bool = False
    confirmed_cloud_export: bool = False


class NotebookResearchNoteRequest(BaseModel):
    reference: str = Field(min_length=2, max_length=80)
    title: str = Field(default="Gemini Notebook 연구노트", max_length=200)
    content: str = Field(min_length=1, max_length=5_242_880)
    sermon_id: int | None = None


class NotebookDriveRequest(BaseModel):
    folder: str = Field(default="", max_length=1000)


def _select_generation_model(client: LMStudioClient, requested: str = "", minutes: int = DEFAULT_SERMON_MINUTES) -> tuple[str, dict]:
    catalog = client.model_catalog()
    generation_models = catalog["generation_models"]
    if requested and requested in generation_models:
        return requested, catalog
    if requested:
        raise RuntimeError(f"선택한 생성 모델이 LM Studio의 READY 목록에 없습니다: {requested}")
    if catalog["source"] == "openai_compatible" and generation_models:
        return recommended_generation_model(minutes, generation_models), catalog
    if catalog["source"] == "native_model_fallback" and generation_models:
        raise RuntimeError("LM Studio의 /v1/models가 비정상이라 보조 모델목록만 확인했습니다. Loaded Models에서 READY인 생성 모델을 화면에서 직접 선택하세요.")
    raise RuntimeError("LM Studio에서 사용할 수 있는 생성 모델을 찾지 못했습니다.")


def _request_reference(value: str) -> str:
    """Normalize a request boundary reference and expose safe client errors."""
    try:
        return normalize_user_reference(value)
    except ValueError as exc:
        raise HTTPException(400, f"중심본문 형식을 확인하세요: {exc}") from exc


def _collect_research_packet(data, client: LMStudioClient) -> dict:
    normalized_reference = normalize_user_reference(data.main_reference) if data.main_reference.strip() else ""
    query = " ".join(x for x in [normalized_reference, data.topic, data.details] if x).strip()
    search_mode = "문자검색"
    search_results = search_passages(query, limit=32)
    doctrine_notes = []
    doctrine_search_mode = "사용 안 함"
    rag = rag_stats()
    if data.use_rag and data.embedding_model and data.embedding_model in rag["models"]:
        try:
            search_results = hybrid_search(query, client, data.embedding_model, limit=32)
            search_mode = "하이브리드 RAG"
        except (ConnectionError, RuntimeError, ValueError):
            search_mode = "문자검색(자동 복귀)"
    if data.use_rag and data.embedding_model and data.embedding_model in rag["doctrine_models"]:
        try:
            denomination_code = getattr(data, "denomination_code", "").strip()
            if denomination_code:
                doctrine_notes = search_approved_doctrine(query, client, data.embedding_model, denomination_code, DB_PATH, limit=6, include_common=True)
                doctrine_search_mode = "승인 교단 V2"
            else:
                doctrine_notes = doctrine_search(query, data.tradition, client, data.embedding_model, limit=6)
                doctrine_search_mode = "기존 전통 RAG"
        except (ConnectionError, RuntimeError, ValueError):
            doctrine_notes = []
            doctrine_search_mode = "교리 검색 오류(근거 제외)"
    packet = build_research_packet(normalized_reference, search_results, doctrine_notes, tradition=data.tradition)
    packet["search_mode"] = search_mode
    packet["embedding_model"] = data.embedding_model
    packet["tradition"] = data.tradition
    packet["denomination_code"] = getattr(data, "denomination_code", "").strip()
    packet["doctrine_search_mode"] = doctrine_search_mode
    packet["social_context_policy"] = build_social_context_policy(data.topic, data.details)
    return packet


def _preflight_result(data: PreflightRequest) -> dict:
    """Return required failures and optional quality warnings without generating text."""
    steps = []

    def add(key: str, label: str, state: str, required: bool, detail: str) -> None:
        steps.append({"key": key, "label": label, "state": state, "required": required, "detail": detail})

    topic = data.topic.strip()
    reference_error = None
    try:
        reference = normalize_user_reference(data.main_reference) if data.main_reference.strip() else ""
    except ValueError as exc:
        reference_error = str(exc)
        reference = ""
    add("request", "설교 요청", "pass" if topic else "fail", True, "주제 입력 완료" if topic else "설교 주제를 입력하세요.")
    add("duration", "설교 시간", "pass", True, f"공식 시간 {data.minutes}분 · {data.reading_cpm}자/분 · 목표 약 {data.minutes * data.reading_cpm:,}자")

    database = db_stats()
    add("database", "성경 DB", "pass" if database.get("passages", 0) else "fail", True,
        f"등록 본문 {int(database.get('passages', 0)):,}건" if database.get("passages", 0) else "등록된 성경 본문이 없습니다.")

    client = LMStudioClient()
    catalog = None
    try:
        catalog = client.model_catalog()
        generation = catalog.get("generation_models") or []
        verified = catalog.get("source") == "openai_compatible"
        if not verified:
            add("lmstudio", "LM Studio 생성 모델", "fail", True, "OpenAI 호환 /v1/models에서 READY 생성 모델을 확인하지 못했습니다.")
        elif data.model and data.model not in generation:
            add("lmstudio", "LM Studio 생성 모델", "fail", True, f"선택 모델이 READY 목록에 없습니다: {data.model}")
        elif generation:
            chosen = data.model or recommended_generation_model(data.minutes, generation)
            client.probe_generation(chosen)
            add("lmstudio", "LM Studio 생성 모델", "pass", True, f"READY · 실제 추론 연결 확인 · {chosen}")
        else:
            add("lmstudio", "LM Studio 생성 모델", "fail", True, "READY 상태의 생성 모델이 없습니다.")
    except (ConnectionError, RuntimeError) as exc:
        add("lmstudio", "LM Studio 생성 모델", "fail", True, str(exc))

    packet = None
    if reference_error:
        add("main_reference", "중심본문", "fail", True, reference_error)
    elif not reference:
        add("main_reference", "중심본문", "fail", True, "중심본문을 입력하세요.")
    elif database.get("passages", 0):
        packet_data = ResearchPacketRequest(
            topic=data.topic, details=data.details, main_reference=reference, tradition=data.tradition,
            embedding_model=data.embedding_model, denomination_code=getattr(data, "denomination_code", ""), use_rag=data.use_rag,
        )
        packet = _collect_research_packet(packet_data, client)
        ready = bool(packet.get("readiness", {}).get("generation_ready"))
        missing = packet.get("missing_main_references") or []
        detail = "중심본문 범위 연속성 확인 완료" if ready else (
            "DB 미등록 절: " + ", ".join(missing) if missing else "범위 전체를 제공하는 단일 번역/자료가 없습니다."
        )
        add("main_reference", "중심본문", "pass" if ready else "fail", True, detail)
    else:
        add("main_reference", "중심본문", "fail", True, "성경 DB를 먼저 준비하세요.")

    rag = rag_stats()
    if not data.use_rag:
        add("rag", "의미검색 RAG", "pass", False, "사용 안 함 · 문자검색으로 생성합니다.")
    elif not data.embedding_model:
        add("rag", "의미검색 RAG", "warn", False, "임베딩 모델을 선택하지 않아 문자검색으로 자동 복귀합니다.")
    else:
        loaded_embeddings = (catalog or {}).get("embedding_models") or []
        indexed = data.embedding_model in (rag.get("models") or [])
        loaded = data.embedding_model in loaded_embeddings
        state = "pass" if loaded and indexed else "warn"
        detail = "임베딩 모델 READY · 성경 RAG 인덱스 준비" if state == "pass" else "임베딩 모델 READY 상태와 선택 모델의 RAG 인덱스를 확인하세요."
        add("rag", "의미검색 RAG", state, False, detail)

    if packet:
        readiness = packet.get("readiness") or {}
        risks = packet.get("original_risk_flags") or []
        original_ok = bool(readiness.get("original_language_ready")) and not risks
        add("original", "히브리어·헬라어", "pass" if original_ok else "warn", False,
            "등록 원어 근거와 출처 확인" if original_ok else (f"원어 출처/뜻 확인 필요 {len(risks)}건" if risks else "등록 원어 근거가 없습니다."))
        translation_policy = packet.get("translation_policy") or {}
        core_ready = bool(translation_policy.get("core_engine_ready"))
        missing_core = translation_policy.get("missing_core") or []
        add("translation_policy", "영어 번역 우선순위", "pass" if core_ready else "warn", False,
            "개역개정·원문·ESV·NASB·NIV·CSB·NET 핵심 엔진 준비" if core_ready
            else "권장 핵심 자료 미등록: " + ", ".join(missing_core or ["통합 근거 패킷 재검사 필요"]))
        social_policy = packet.get("social_context_policy") or build_social_context_policy(data.topic, data.details)
        add("social_neutrality", "시대·정치 적용 중립성", "pass", False,
            "사회·정치·세계정세 감지 · 공의·사랑·화해·책임 가드 활성" if social_policy.get("active")
            else "항상 적용 · 특정 정당·정치인 편향과 근거 없는 시사 단정 방지")
        doctrine_ok = bool(readiness.get("doctrine_ready"))
        add("doctrine", "교리·신학 전통", "pass" if doctrine_ok else "warn", False,
            "선택 전통과 교리 근거 정합성 확인" if doctrine_ok else "교리 RAG 근거가 없거나 선택 전통 정합성을 확인해야 합니다.")
        quality = packet.get("evidence_completeness") or {}
        score = int(quality.get("score") or 0)
        add("quality", "근거 완성도", "pass" if score >= 60 else "warn", False,
            f"{score}점 · {quality.get('label', '')} · 신학적 정확도 점수가 아닌 자료 준비 지표")
    else:
        add("original", "히브리어·헬라어", "warn", False, "중심본문 준비 후 확인합니다.")
        add("translation_policy", "영어 번역 우선순위", "warn", False, "중심본문 준비 후 1·2·3군 역할을 확인합니다.")
        add("social_neutrality", "시대·정치 적용 중립성", "pass", False,
            "항상 적용 · 공의·사랑·화해·책임 기준으로 중립성을 점검합니다.")
        add("doctrine", "교리·신학 전통", "warn", False, "중심본문 준비 후 확인합니다.")
        add("quality", "근거 완성도", "warn", False, "중심본문 준비 후 계산합니다.")

    failures = [x for x in steps if x["required"] and x["state"] == "fail"]
    warnings = [x for x in steps if x["state"] == "warn"]
    return {"ready": not failures, "steps": steps, "required_failures": len(failures), "warnings": len(warnings), "packet": packet}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if session_user(request.cookies.get("sermon_session")) is None:
        login_path = ROOT / "templates" / "login.html"
        if login_path.is_file():
            return login_path.read_text(encoding="utf-8")
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    enabled = os.getenv("GROUNDING_DASHBOARD_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    report_enabled = os.getenv("GROUNDING_REPORT_EXPORT_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    return html.replace("</head>", f"<script>window.GROUNDING_DASHBOARD_ENABLED={str(enabled).lower()};window.GROUNDING_REPORT_EXPORT_ENABLED={str(report_enabled).lower()};</script></head>")


@app.get("/api/project-summary")
def project_summary():
    return build_project_summary(ROOT, APP_VERSION)


# Compatibility implementations retained below; routes are registered by bible_router.
def original_coverage(reference: str):
    try:
        return original_language_coverage(reference)
    except ValueError as exc:
        raise HTTPException(400, f"원어 준비상태 확인 실패: {exc}") from exc


@app.get("/api/readiness")
def runtime_readiness():
    """실사용에 필요한 로컬 구성요소를 한 화면에서 진단한다."""
    steps = []

    def add(key: str, label: str, state: str, required: bool, detail: str) -> None:
        steps.append({"key": key, "label": label, "state": state, "required": required, "detail": detail})

    add("duration", "15분 기본 설정", "pass" if DEFAULT_SERMON_MINUTES == 15 and 15 in SUPPORTED_SERMON_MINUTES else "fail", True,
        f"기본 {DEFAULT_SERMON_MINUTES}분 · 선택 {', '.join(map(str, SUPPORTED_SERMON_MINUTES))}분")
    database = db_stats()
    passage_count = int(database.get("passages", 0))
    add("database", "성경 DB", "pass" if passage_count else "fail", True,
        f"등록 본문 {passage_count:,}건" if passage_count else "등록 본문 0건 · 사용권을 확인한 성경 자료를 먼저 가져오세요.")

    catalog = None
    try:
        catalog = LMStudioClient().model_catalog()
        generation = catalog.get("generation_models") or []
        verified = catalog.get("source") == "openai_compatible"
        state = "pass" if verified and generation else "fail"
        detail = f"OpenAI 호환 READY 생성 모델 {len(generation)}개" if state == "pass" else "LM Studio /v1/models에서 READY 생성 모델을 확인하지 못했습니다."
        add("lmstudio", "LM Studio 0.4.x", state, True, detail)
    except (ConnectionError, RuntimeError) as exc:
        add("lmstudio", "LM Studio 0.4.x", "fail", True, str(exc))

    embeddings = (catalog or {}).get("embedding_models") or []
    rag = rag_stats()
    rag_ready = bool(embeddings and set(embeddings).intersection(rag.get("models") or []))
    add("rag", "의미검색 RAG", "pass" if rag_ready else "warn", False,
        "READY 임베딩 모델과 성경 인덱스 확인" if rag_ready else "선택 기능 · 준비되지 않아도 문자검색으로 설교 생성은 가능합니다.")

    pdf = pdf_environment_status()
    if pdf["ready"]:
        engine_label = "WeasyPrint" if pdf.get("engine") == "weasyprint" else "ReportLab (Windows 대체 엔진)"
        font_label = pdf.get("font_family") or "한글 로컬 글꼴"
        pdf_detail = f"{engine_label} · {font_label} 준비 완료"
    elif not pdf["engine_ready"]:
        pdf_detail = "PDF 엔진을 사용할 수 없습니다. requirements-pdf.txt를 다시 설치하세요."
    else:
        pdf_detail = "한글 글꼴이 없습니다. fonts에 Nanum TTF를 추가하세요. Windows 맑은 고딕도 자동 인식합니다."
    add("pdf", "PDF 출력", "pass" if pdf["ready"] else "warn", False, pdf_detail)

    output_ready = EXPORTS.exists() and os.access(EXPORTS, os.W_OK)
    add("storage", "로컬 저장 폴더", "pass" if output_ready else "fail", True,
        "출력 폴더 쓰기 가능" if output_ready else "출력 폴더에 쓸 수 없습니다.")
    portable_data = bool(getattr(sys, "frozen", False))
    add("data_portability", "업데이트 데이터 보호", "pass" if portable_data else "warn", False,
        "공용 LocalAppData에 저장되어 새 EXE로 교체해도 유지됩니다." if portable_data else
        "ZIP 실행 데이터는 현재 프로그램 폴더에 저장됩니다. 새 버전으로 이동하기 전에 통합 백업을 다운로드하세요.")
    github = github_readiness(ROOT, DB_PATH)
    add("github", "GitHub 연결", github["state"], False, github["detail"])
    required_failures = [x for x in steps if x["required"] and x["state"] == "fail"]
    return {
        "app_version": APP_VERSION,
        "ready_for_generation": not required_failures,
        "ready_for_full_output": not required_failures and pdf["ready"],
        "required_failures": len(required_failures),
        "warnings": sum(1 for x in steps if x["state"] == "warn"),
        "steps": steps,
        "lmstudio_url": get_lmstudio_url(),
        "user_data_root": str(USER_ROOT),
        "pdf": pdf,
        "github": github,
    }


# Compatibility implementations retained below; routes are registered by settings_router.
def lmstudio_settings():
    return {"base_url": get_lmstudio_url()}


def recover_lmstudio(data: LMStudioRecoveryRequest):
    client = LMStudioClient(timeout=20)
    steps = []
    try:
        catalog = client.model_catalog()
        openai_ok = catalog.get("source") == "openai_compatible"
        steps.append({"key": "server", "ok": openai_ok, "label": "Local Server", "detail": "OpenAI 호환 /v1/models 응답 정상" if openai_ok else (catalog.get("openai_error") or "OpenAI 호환 모델 목록을 읽지 못했습니다.")})
        generation = catalog.get("generation_models") or []
        model = data.model.strip()
        model_ok = bool(model and model in generation)
        steps.append({"key": "model", "ok": model_ok, "label": "생성 모델", "detail": f"READY · {model}" if model_ok else ("화면에서 READY 생성 모델을 다시 선택하세요." if generation else "LM Studio Loaded Models에 READY 생성 모델이 없습니다.")})
        if not openai_ok or not model_ok:
            return {"ok": False, "ready": False, "base_url": get_lmstudio_url(), "steps": steps, "generation_models": generation, "message": "LM Studio 설정을 확인한 뒤 다시 점검하세요."}
        client.probe_generation(model)
        steps.append({"key": "inference", "ok": True, "label": "실제 추론", "detail": "/v1/chat/completions 응답 정상"})
        return {"ok": True, "ready": True, "base_url": get_lmstudio_url(), "steps": steps, "generation_models": generation, "model": model, "message": "실제 추론 연결이 복구되었습니다. Preflight를 다시 실행하세요."}
    except (ConnectionError, RuntimeError) as exc:
        steps.append({"key": "inference", "ok": False, "label": "실제 추론", "detail": str(exc)})
        return {"ok": False, "ready": False, "base_url": get_lmstudio_url(), "steps": steps, "generation_models": [], "message": str(exc)}


def start_lmstudio_server():
    """Explicitly start only LM Studio's localhost API; never load/substitute a model."""
    base_url = get_lmstudio_url()
    try:
        result = start_local_server(base_url)
        result["base_url"] = base_url
        result["ok"] = bool(result.get("port_open"))
        if result["port_open"]:
            try:
                catalog = LMStudioClient(base_url=base_url, timeout=5).model_catalog()
                result["api_ready"] = catalog.get("source") == "openai_compatible"
                result["generation_models"] = catalog.get("generation_models") or []
                if not result["api_ready"]:
                    result["message"] += " 포트는 열렸지만 OpenAI 호환 /v1/models 응답이 아닙니다."
                elif not result["generation_models"]:
                    result["message"] += " 서버는 정상이며, 이제 LM Studio에서 생성 모델을 Load해야 합니다."
            except (ConnectionError, RuntimeError) as exc:
                result["api_ready"] = False
                result["generation_models"] = []
                result["message"] += f" API 확인 실패: {exc}"
        else:
            result["api_ready"] = False
            result["generation_models"] = []
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def lmstudio_diagnostics():
    base_url = get_lmstudio_url()
    try:
        port = local_api_port(base_url)
    except ValueError as exc:
        return {"ok": False, "base_url": base_url, "cli_found": False, "port_open": False, "cause": "invalid_url", "message": str(exc)}
    cli = find_lms_cli()
    opened = port_is_open(port)
    cause = "unknown"
    message = "LM Studio API를 확인할 수 없습니다."
    if not opened and cli is None:
        cause, message = "cli_missing", "LM Studio CLI를 찾지 못했습니다. LM Studio를 설치하고 한 번 실행하세요."
    elif not opened:
        cause, message = "server_stopped", "LM Studio는 설치되어 있지만 Local Server 포트가 닫혀 있습니다. 자동 시작 버튼을 누르세요."
    else:
        try:
            catalog = LMStudioClient(base_url=base_url, timeout=5).model_catalog()
            generation = catalog.get("generation_models") or []
            if catalog.get("source") != "openai_compatible":
                cause, message = "wrong_service", f"포트 {port}는 열렸지만 LM Studio OpenAI 호환 API가 아닙니다."
            elif not generation:
                cause, message = "model_not_loaded", "Local Server는 정상이나 READY 생성 모델이 없습니다. LM Studio에서 모델을 Load하세요."
            else:
                cause, message = "ready", f"Local Server와 READY 생성 모델 {len(generation)}개를 확인했습니다."
            return {"ok": cause == "ready", "base_url": base_url, "cli_found": cli is not None, "cli": str(cli or ""), "port": port, "port_open": True, "cause": cause, "generation_models": generation, "message": message}
        except (ConnectionError, RuntimeError) as exc:
            cause, message = "api_error", str(exc)
    return {"ok": False, "base_url": base_url, "cli_found": cli is not None, "cli": str(cli or ""), "port": port, "port_open": opened, "cause": cause, "generation_models": [], "message": message}


@app.get("/api/import/presets")
def bible_import_presets():
    return {
        "items": PUBLIC_BIBLE_IMPORT_PRESETS,
        "format": {
            "required": ["reference", "text"],
            "optional_reference_parts": ["book", "chapter", "verse"],
            "max_items_per_request": 5000,
            "supported_source_formats": list(SUPPORTED_SOURCE_FORMATS),
            "supported_archive_formats": ["usfm_zip"],
        },
        "notice": "본문 파일 자체의 배포조건과 출처를 사용자가 확인한 뒤 가져오세요. 개역개정·쉬운성경 본문은 프로그램에 포함하지 않습니다.",
    }


@app.post("/api/import/convert")
def convert_bible_file(data: BibleConvertRequest):
    try:
        resolved, items = convert_bible_source(data.content, data.source_format)
        return {"ok": True, "source_format": resolved, "count": len(items), "items": items}
    except ValueError as exc:
        raise HTTPException(400, f"성경 원본 변환 실패: {exc}") from exc


@app.post("/api/import/convert-usfm-zip")
async def convert_bible_usfm_zip(request: Request):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_ZIP_UPLOAD_BYTES:
                raise HTTPException(413, "USFM ZIP은 최대 50MB까지 변환할 수 있습니다.")
        except ValueError:
            raise HTTPException(400, "Content-Length 값이 올바르지 않습니다.")
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > MAX_ZIP_UPLOAD_BYTES:
            raise HTTPException(413, "USFM ZIP은 최대 50MB까지 변환할 수 있습니다.")
    try:
        items, files = convert_usfm_zip(bytes(payload))
        return {
            "ok": True,
            "source_format": "usfm_zip",
            "count": len(items),
            "file_count": len(files),
            "files": files,
            "items": items,
        }
    except ValueError as exc:
        raise HTTPException(400, f"USFM ZIP 변환 실패: {exc}") from exc


def update_lmstudio_settings(data: LMStudioSettingsRequest):
    try:
        base_url = set_lmstudio_url(data.base_url)
        catalog = LMStudioClient(base_url=base_url, timeout=5).model_catalog()
        return {"ok": True, "connected": bool(catalog["models"]), "base_url": base_url, **catalog}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ConnectionError as exc:
        return {"ok": True, "connected": False, "base_url": get_lmstudio_url(), "models": [], "message": str(exc)}


def reading_speed():
    return {"chars_per_minute": get_reading_cpm()}


def update_reading_speed(data: ReadingSpeedRequest):
    return {"ok": True, "chars_per_minute": set_reading_cpm(data.chars_per_minute)}


def calibrate_speed(data: ReadingCalibrationRequest):
    try:
        return {"ok": True, "chars_per_minute": calibrate_reading_cpm(data.text, data.seconds)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# Compatibility implementations retained below; routes are registered by projects_router.
def projects_dashboard():
    return project_dashboard()


def workflow_config():
    reading_cpm = get_reading_cpm()
    return {
        "version": 40,
        "app_version": APP_VERSION,
        "minutes": list(SUPPORTED_SERMON_MINUTES),
        "default_minutes": DEFAULT_SERMON_MINUTES,
        "reading_cpm": reading_cpm,
        "target_characters": {str(m): m * reading_cpm for m in SUPPORTED_SERMON_MINUTES},
        "recommended_generation_models": {str(minutes): list(models) for minutes, models in RECOMMENDED_GENERATION_MODELS.items()},
        "steps": ["brief", "bible", "languages", "draft", "evidence", "review", "final"],
    }


def version_workflow(sermon_id: int, version: int):
    try:
        return sermon_workflow_status(sermon_id, version)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


def project_detail(sermon_id: int):
    if not any(item["id"] == sermon_id for item in list_sermons()):
        raise HTTPException(404, "설교 프로젝트를 찾을 수 없습니다.")
    return get_project_meta(sermon_id)


def save_project_detail(sermon_id: int, data: ProjectMetaRequest):
    if data.service_date:
        try:
            datetime.strptime(data.service_date, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(400, "예배일은 YYYY-MM-DD 형식으로 입력하세요.") from exc
    try:
        return {"ok": True, **update_project_meta(sermon_id, **data.model_dump())}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


# Compatibility implementations retained below; routes are registered by bible_router.
def create_passage(data: PassageRequest):
    try:
        add_passage(data.translation, data.language, data.reference, data.text, data.license_note)
    except ValueError as exc:
        raise HTTPException(403, str(exc)) from exc
    return {"ok": True}


def bulk_import(data: BulkImportRequest):
    try:
        return {"ok": True, "imported": import_items([item.model_dump() for item in data.items])}
    except ValueError as exc:
        raise HTTPException(403, str(exc)) from exc


def database_dashboard():
    return bible_database_dashboard()


@app.get("/api/original-language/dashboard")
def original_language_dashboard_api():
    return original_language_dashboard()


def database_integrity():
    return bible_database_integrity()


@app.delete("/api/database/translation")
def remove_database_translation(translation: str, confirm: str = ""):
    if confirm != translation:
        raise HTTPException(400, "삭제 확인값이 번역/자료명과 일치하지 않습니다.")
    try:
        result = delete_bible_translation(translation)
        return {"ok": True, **result, "dashboard": bible_database_dashboard()}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/backups")
def backups():
    try:
        return {"items": list_backups(BACKUPS_DIR), "max_upload_bytes": 512 * 1024 * 1024}
    except OSError as exc:
        raise HTTPException(500, f"백업 폴더를 읽을 수 없습니다: {exc}") from exc


@app.post("/api/backups")
def make_backup():
    try:
        item = create_backup(DB_PATH, BACKUPS_DIR, APP_VERSION, reason="manual")
        return {"ok": True, **item, "url": f"/api/backups/download/{item['filename']}"}
    except (BackupError, OSError) as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/backups/download/{filename}")
def download_backup(filename: str):
    safe = Path(filename).name
    if filename != safe or not safe.startswith("sermon_backup_") or not safe.endswith(".zip"):
        raise HTTPException(400, "올바르지 않은 백업 파일명입니다.")
    path = BACKUPS_DIR / safe
    if not path.is_file():
        raise HTTPException(404, "백업 파일을 찾을 수 없습니다.")
    return FileResponse(path, filename=safe, media_type="application/zip")


@app.post("/api/backups/restore")
async def restore_uploaded_backup(request: Request, confirm: str = ""):
    if confirm != "RESTORE":
        raise HTTPException(400, "복원 확인값이 올바르지 않습니다.")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 512 * 1024 * 1024:
                raise HTTPException(413, "백업 파일은 최대 512MB까지 복원할 수 있습니다.")
        except ValueError:
            raise HTTPException(400, "Content-Length 값이 올바르지 않습니다.")
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    upload = BACKUPS_DIR / f"restore_upload_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.zip"
    size = 0
    try:
        with upload.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 512 * 1024 * 1024:
                    raise HTTPException(413, "백업 파일은 최대 512MB까지 복원할 수 있습니다.")
                handle.write(chunk)
        if size == 0:
            raise HTTPException(400, "선택한 백업 파일이 비어 있습니다.")
        try:
            result = restore_backup(upload, DB_PATH, BACKUPS_DIR, APP_VERSION)
            init_db(DB_PATH)
            return {"ok": True, **result, "database": bible_database_dashboard()}
        except BackupError as exc:
            raise HTTPException(400, str(exc)) from exc
    finally:
        upload.unlink(missing_ok=True)


@app.post("/api/import/bible")
def wizard_bible_import(data: BibleWizardImportRequest):
    if not data.confirmed:
        raise HTTPException(400, "출처와 사용조건 확인에 동의해야 가져올 수 있습니다.")
    preset = next((item for item in PUBLIC_BIBLE_IMPORT_PRESETS if item["id"] == data.preset_id), None)
    if preset is None:
        raise HTTPException(400, "지원하지 않는 성경 자료 프리셋입니다.")
    if preset["kind"] == "licensed_custom":
        translation = data.translation.strip()
        language = data.language.strip()
        license_note = data.license_note.strip()
        source_url = data.source_url.strip()
        if not all((translation, language, license_note, source_url)):
            raise HTTPException(400, "사용자 허가자료는 번역명, 언어, 사용조건, 공식 출처 URL을 모두 입력하세요.")
        license_row = next((row for row in translation_licenses() if row["translation"] == translation), None)
        if not license_row or not bool(license_row["allow_fulltext"]):
            raise HTTPException(403, "사용자 허가자료는 먼저 아래 사용권 등록부에 같은 번역명을 등록하고 '전문 DB 저장 허용'을 켜야 합니다.")
    else:
        translation = preset["translation"]
        language = preset["language"]
        license_note = preset["license_note"]
        source_url = preset["source_url"]
    recorded_license = f"{license_note} · 출처: {source_url}"
    try:
        imported = import_items([
            {
                "translation": translation,
                "language": language,
                "reference": item.reference,
                "text": item.text,
                "license_note": recorded_license,
            }
            for item in data.items
        ])
    except ValueError as exc:
        raise HTTPException(403, str(exc)) from exc
    return {"ok": True, "imported": imported, "translation": translation, "database": db_stats()}


def compare(reference: str):
    return {"reference": reference, "items": compare_reference(reference)}


@app.get("/api/study")
def study_passage(reference: str, model: str = "", limit: int = 6):
    reference = reference.strip()
    if not reference:
        raise HTTPException(400, "중심본문을 입력하세요.")
    related = []
    related_mode = "not_requested"
    if model:
        if model not in rag_stats()["models"]:
            related_mode = "index_required"
        else:
            try:
                related = recommend_related(reference, LMStudioClient(), model, min(max(limit, 1), 12))
                related_mode = "semantic_rag"
            except (ConnectionError, RuntimeError, ValueError) as exc:
                raise HTTPException(503, f"본문 연구 관련구절 검색 실패: {exc}") from exc
    result = build_passage_study(reference, related)
    result["related_mode"] = related_mode
    if related_mode == "index_required":
        result["warnings"].append("선택한 임베딩 모델의 RAG 인덱스를 먼저 만들어야 관련구절을 검색할 수 있습니다.")
        result["note_markdown"] += "\n- RAG 인덱스가 없어 관련구절 의미검색을 생략했습니다."
    return result


@app.post("/api/research/packet")
def research_packet(data: ResearchPacketRequest):
    """Preview the exact evidence path that sermon generation will use."""
    data = data.model_copy(update={"main_reference": _request_reference(data.main_reference)})
    packet = _collect_research_packet(data, LMStudioClient())
    if not packet["readiness"]["generation_ready"]:
        if packet.get("missing_main_references"):
            packet["warnings"].insert(0, "중심본문 범위에 DB 미등록 절이 있어 설교 생성 준비가 완료되지 않았습니다.")
        else:
            packet["warnings"].insert(0, "중심본문 범위 전체를 연속해서 제공하는 단일 번역/자료가 없어 설교 생성 준비가 완료되지 않았습니다.")
    return packet


@app.get("/api/notebooklm/status")
def notebooklm_status(reference: str = ""):
    drive = drive_status(DB_PATH)
    notes = list_research_notes(normalize_reference(reference), DB_PATH) if reference.strip() else []
    return {
        "mode": "general-notebook-file-bridge",
        "drive": drive,
        "notes": notes,
        "cloud_api_used": False,
        "notice": "Google Drive 데스크톱의 로컬 동기화 폴더만 사용하며 Google 계정 비밀번호나 API 키를 저장하지 않습니다.",
    }


@app.put("/api/notebooklm/drive")
def notebooklm_drive_settings(data: NotebookDriveRequest):
    try:
        return {"ok": True, **set_drive_folder(data.folder, DB_PATH)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/notebooklm/pack")
def notebooklm_pack(data: NotebookPackRequest):
    if not data.confirmed_cloud_export:
        raise HTTPException(400, "저작권·개인정보·클라우드 전송 주의사항을 확인해야 자료팩을 만들 수 있습니다.")
    try:
        reference = _request_reference(data.main_reference)
        packet = build_research_packet(reference)
        if not packet.get("readiness", {}).get("generation_ready"):
            missing = packet.get("missing_main_references") or []
            detail = "DB 미등록 절: " + ", ".join(missing) if missing else "중심본문 범위 전체를 제공하는 단일 번역/자료가 없습니다."
            raise ValueError("NotebookLM 자료팩을 만들 중심본문이 준비되지 않았습니다. " + detail)
        result = create_pack(
            packet, topic=data.topic.strip(), reference=reference, minutes=data.minutes,
            tradition=data.tradition, exports_dir=EXPORTS, db_path=DB_PATH,
            sync_to_drive=data.sync_to_drive,
        )
        return {"ok": True, **result, "url": f"/api/notebooklm/pack/download/{result['filename']}"}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(500, f"자료팩 파일을 저장할 수 없습니다: {exc}") from exc


@app.get("/api/notebooklm/pack/download/{filename}")
def notebooklm_pack_download(filename: str):
    safe = Path(filename).name
    if filename != safe or not safe.startswith("NotebookLM_") or not safe.endswith(".zip"):
        raise HTTPException(400, "올바르지 않은 NotebookLM 자료팩 파일명입니다.")
    path = EXPORTS / safe
    if not path.is_file():
        raise HTTPException(404, "NotebookLM 자료팩을 찾을 수 없습니다.")
    return FileResponse(path, filename=safe, media_type="application/zip")


@app.post("/api/notebooklm/notes")
def notebooklm_note(data: NotebookResearchNoteRequest):
    try:
        reference = normalize_reference(data.reference)
        result = import_research_note(
            reference=reference, title=data.title, content=data.content,
            sermon_id=data.sermon_id, db_path=DB_PATH,
        )
        return {
            "ok": True, **result,
            "message": "인용 표시를 찾았습니다. 목회자가 등록 근거와 대조해야 합니다." if result["citation_count"] else "인용 표시가 없어 미검증 연구노트로 저장했습니다.",
        }
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/notebooklm/notes")
def notebooklm_notes(reference: str):
    try:
        normalized = normalize_reference(reference)
        return {"reference": normalized, "items": list_research_notes(normalized, DB_PATH)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/preflight")
def preflight_check(data: PreflightRequest):
    return _preflight_result(data)


@app.post("/api/outline")
def create_outline(data: SermonOutlineRequest, request: Request = None):
    try:
        normalized_reference = _request_reference(data.main_reference)
    except HTTPException:
        raise
    packet = build_research_packet(normalized_reference)
    study = packet["study"]
    evidence = list(packet.get("bible_sources") or [])
    if not packet.get("readiness", {}).get("generation_ready"):
        missing = packet.get("missing_main_references") or []
        if missing:
            raise HTTPException(400, "설교 구조에 필요한 중심본문 절이 DB에 없습니다: " + ", ".join(missing))
        raise HTTPException(400, "중심본문 각 절은 있지만 요청 범위 전체를 연속 제공하는 단일 번역/자료가 없습니다.")
    reading_cpm = data.reading_cpm or get_reading_cpm()
    time_plan = sermon_time_plan(data.minutes, reading_cpm)
    client = LMStudioClient()
    client.begin_generation(request.headers.get("X-Generation-Id", "") if request else "")
    try:
        model, _ = _select_generation_model(client, data.model, data.minutes)
        prompt_study = compact_outline_study(study)
        system, user = build_outline_prompt(data.model_dump(), prompt_study, time_plan)
        prompt_mode = "8K-safe"
        try:
            raw_outline = client.chat(model, system, user, temperature=0.12)
        except ConnectionError as exc:
            if "컨텍스트 한도 초과" not in str(exc):
                raise
            prompt_study = compact_outline_study(study, aggressive=True)
            system, user = build_outline_prompt(data.model_dump(), prompt_study, time_plan)
            raw_outline = client.chat(model, system, user, temperature=0.12)
            prompt_mode = "8K-emergency"
        parsed = _parse_json_response(raw_outline)
        outline = validate_sermon_outline(parsed, evidence)
    except ValueError as exc:
        raise HTTPException(422, f"설교 구조 검증 실패: {exc}") from exc
    except (ConnectionError, RuntimeError) as exc:
        raise HTTPException(503, str(exc)) from exc
    finally:
        client.end_generation()
    return {
        "outline": outline, "time_plan": time_plan, "model": model,
        "reference": normalized_reference, "study_counts": study.get("counts", {}),
        "prompt_budget": {
            "input_chars": len(system) + len(user),
            "bible_used": len(prompt_study.get("translations", [])) + len(prompt_study.get("context", [])),
            "bible_total": len(study.get("translations", [])) + len(study.get("context", [])),
            "original_used": len(prompt_study.get("original_notes", [])),
            "original_total": len(study.get("original_notes", [])),
            "mode": prompt_mode,
        },
    }


@app.post("/api/original-notes")
def create_original_note(data: OriginalNoteRequest):
    try:
        verses = expand_reference(data.reference)
        if len(verses) != 1:
            raise ValueError("원어 근거 추가는 한 절 단위로 입력하세요. 범위 조회는 '이 본문 원어 근거 보기'에서 지원합니다.")
        validate_primary_original_language(data.reference, data.language)
        payload = data.model_dump()
        payload["reference"] = normalize_reference(data.reference)
        note_id = add_original_note(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "id": note_id}


@app.get("/api/original-notes")
def list_original_notes(reference: str):
    return {"reference": reference, "items": original_notes(reference)}


@app.get("/api/reference-info")
def reference_info(reference: str):
    try:
        parsed = parse_reference(reference)
        normalized = normalize_reference(reference)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    language = primary_original_language(reference)
    return {
        "reference": normalized,
        "first_reference": f"{parsed.book} {parsed.chapter}:{parsed.start_verse}",
        "book": parsed.book,
        "is_range": parsed.start_verse != parsed.end_verse,
        "testament": "NT" if language == "grc" else "OT" if language == "he" else "unknown",
        "primary_original_language": language,
    }


@app.get("/api/bible/greek/{book}/{chapter}/{verse}")
def greek_tokens_api(book: str, chapter: int, verse: int):
    try:
        return get_greek_tokens(f"{book} {chapter}:{verse}")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/bible/greek/{book}/{chapter}/{verse}/morphology")
def greek_morphology_api(book: str, chapter: int, verse: int):
    try:
        return get_greek_tokens(f"{book} {chapter}:{verse}")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/bible/greek/{book}/{chapter}/{verse}/apparatus")
def greek_apparatus_api(book: str, chapter: int, verse: int):
    try:
        return get_apparatus_notes(f"{book} {chapter}:{verse}")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/bible/greek/{book}/{chapter}/{verse}/alignment")
def greek_alignment_api(book: str, chapter: int, verse: int):
    try:
        return align_reference(f"{book} {chapter}:{verse}")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/bible/greek/{book}/{chapter}/{verse}/text")
def greek_text_api(book: str, chapter: int, verse: int):
    try:
        return get_greek_text(f"{book} {chapter}:{verse}")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/bible/greek/search/lemma")
def greek_lemma_search_api(lemma: str, limit: int = 50):
    try:
        return lemma_search(lemma, limit=limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/bible/greek/search/normalized")
def greek_normalized_search_api(word: str, limit: int = 50):
    try:
        return normalized_search(word, limit=limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/import/original-notes/convert")
def convert_original_notes_file(data: OriginalNoteConvertRequest):
    try:
        resolved, items = convert_original_note_source(data.content, data.source_format)
        return {"ok": True, "source_format": resolved, "count": len(items), "items": items}
    except ValueError as exc:
        raise HTTPException(400, f"원어 근거 변환 실패: {exc}") from exc


@app.post("/api/import/original-notes")
def bulk_original_notes(data: OriginalNoteBulkRequest):
    if not data.confirmed:
        raise HTTPException(400, "원어 자료의 출처와 사용조건 확인에 동의해야 가져올 수 있습니다.")
    try:
        result = import_original_notes(
            [item.model_dump() for item in data.items], data.source, data.license_note
        )
        return {"ok": True, **result}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/import/original-notes/oshb-zip/preview")
async def preview_oshb_original_zip(request: Request):
    data = await request.body()
    try:
        books = []
        total = 0
        sample = []
        for filename, items in iter_oshb_zip_original_files(data):
            books.append({"file": filename, "count": len(items)})
            total += len(items)
            if len(sample) < 6:
                sample.extend(items[: 6 - len(sample)])
        return {"ok": True, "source_format": "oshb_zip", "book_count": len(books), "count": total, "books": books, "sample": sample}
    except ValueError as exc:
        raise HTTPException(400, f"OSHB ZIP 검사 실패: {exc}") from exc


@app.post("/api/import/original-notes/oshb-zip")
async def import_oshb_original_zip(request: Request):
    source = str(request.query_params.get("source", "")).strip()
    license_note = str(request.query_params.get("license_note", "")).strip()
    confirmed = str(request.query_params.get("confirmed", "")).lower() == "true"
    if not confirmed:
        raise HTTPException(400, "OSHB 원어 자료의 출처와 사용조건 확인에 동의해야 가져올 수 있습니다.")
    data = await request.body()
    progress = {"books": 0}
    try:
        def batches():
            for _, items in iter_oshb_zip_original_files(data):
                progress["books"] += 1
                yield items
        result = import_original_note_batches(batches(), source, license_note)
        return {"ok": True, **result, "book_count": progress["books"]}
    except ValueError as exc:
        raise HTTPException(400, f"OSHB ZIP 등록 실패: {exc}") from exc


@app.post("/api/import/original-lexicon/convert")
def convert_original_lexicon_file(data: LexiconConvertRequest):
    try:
        resolved, items = convert_lexicon_source(data.content, data.source_format)
        return {"ok": True, "source_format": resolved, "count": len(items), "items": items}
    except ValueError as exc:
        raise HTTPException(400, f"원어 사전 변환 실패: {exc}") from exc


@app.post("/api/import/original-language/classify")
def classify_original_language_file(data: OriginalLanguageClassifyRequest):
    role = classify_original_language_source(data.content, data.filename)
    targets = {
        "sblgnt_bible": {"target": "bible_passages", "format": "sblgnt_xml", "label": "SBLGNT 헬라어 성경 본문"},
        "morphgnt_original": {"target": "original_notes", "format": "morphgnt", "label": "MorphGNT 원어 근거"},
        "oshb_original": {"target": "original_notes", "format": "oshb_osis", "label": "OSHB 원어 근거"},
        "original_notes": {"target": "original_notes", "format": "auto", "label": "원어 근거 표"},
        "lexicon": {"target": "lexicon", "format": "auto", "label": "lemma 뜻/음역 사전"},
        "strongs_greek_lexicon": {"target": "lexicon", "format": "strongs_greek_xml", "label": "Strong 헬라어 뜻/음역 사전"},
        "hebrew_strongs_lexicon": {"target": "lexicon", "format": "hebrew_strongs_xml", "label": "Strong 히브리어 뜻/음역 사전"},
        "structured_candidate": {"target": "inspect", "format": "auto", "label": "JSON 구조 검사 필요"},
        "unknown": {"target": "inspect", "format": "auto", "label": "형식 검사 필요"},
    }
    return {"ok": True, "role": role, **targets[role]}


@app.post("/api/import/original-language/install-official")
def install_official_original_language():
    """Start the official SBLGNT/MorphGNT staging and import job."""
    return {"ok": True, **start_install()}


@app.get("/api/import/original-language/install-official/status")
def official_original_language_status():
    return {"ok": True, **installer_status()}


@app.post("/api/import/original-lexicon")
def bulk_original_lexicon(data: LexiconBulkRequest):
    if not data.confirmed:
        raise HTTPException(400, "원어 사전의 출처와 사용조건 확인에 동의해야 가져올 수 있습니다.")
    try:
        result = import_original_lexicon(
            [item.model_dump() for item in data.items], data.source, data.license_note
        )
        return {"ok": True, **result, "stats": original_lexicon_stats()}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/original-lexicon/stats")
def lexicon_stats():
    return original_lexicon_stats()


# Compatibility implementations retained below; routes are registered by doctrine_router.
def create_doctrine(data: DoctrineChunkRequest):
    return {"ok": True, "id": add_doctrine_chunk(data.model_dump())}


def create_translation_license(data: TranslationLicenseRequest):
    register_translation_license(data.model_dump())
    return {"ok": True}


def list_translation_licenses():
    return {"items": translation_licenses()}


def recommend(reference: str, model: str, limit: int = 8):
    if model not in rag_stats()["models"]:
        raise HTTPException(400, "선택한 임베딩 모델의 RAG 인덱스를 먼저 만드세요.")
    try:
        items = recommend_related(reference, LMStudioClient(), model, min(max(limit, 1), 20))
        return {"reference": reference, "model": model, "items": items}
    except (ConnectionError, RuntimeError, ValueError) as exc:
        raise HTTPException(503, f"관련구절 추천 실패: {exc}") from exc


@app.post("/api/rag/reindex")
def reindex_rag(data: RagIndexRequest):
    database = db_stats()
    if database["passages"] < 1:
        raise HTTPException(
            400,
            "성경 자료가 0건입니다. 먼저 '성경 자료 추가'에서 본문을 등록하거나 JSON Import한 뒤 RAG 인덱스를 만드세요.",
        )
    client = LMStudioClient()
    try:
        count = build_rag_index(client, data.model)
        doctrine_count = build_doctrine_index(client, data.model)
        return {"ok": True, "indexed": count, "doctrine_indexed": doctrine_count, "model": data.model, "rag": rag_stats()}
    except (ConnectionError, RuntimeError) as exc:
        raise HTTPException(503, f"RAG 인덱스 생성 실패: {exc}") from exc


@app.post("/api/sermons")
def generate_sermon(data: SermonRequest, request: Request = None):
    if db_stats()["passages"] < 1:
        raise HTTPException(
            400,
            "등록된 성경 근거가 0건이라 근거 기반 설교를 생성할 수 없습니다. 먼저 성경 자료를 등록하세요.",
        )
    if not data.main_reference.strip():
        raise HTTPException(400, "근거 기반 설교를 생성하려면 중심본문을 입력하세요.")
    data = data.model_copy(update={"main_reference": _request_reference(data.main_reference)})
    client = LMStudioClient()
    client.begin_generation(request.headers.get("X-Generation-Id", "") if request else "")
    reading_cpm = data.reading_cpm or get_reading_cpm()
    if data.main_reference:
        packet = _collect_research_packet(data, client)
        if not packet["readiness"]["generation_ready"]:
            missing = ", ".join(packet.get("missing_main_references") or [])
            if missing:
                raise HTTPException(400, f"중심본문 전체가 DB에 등록되어야 설교를 생성할 수 있습니다. 누락: {missing}")
            raise HTTPException(400, "범위 중심본문은 최소 한 번역/자료가 요청 범위 전체를 연속해서 제공해야 설교를 생성할 수 있습니다.")
        passages = list(packet["bible_sources"])
        word_notes = list(packet["original_notes"])
        doctrine_notes = list(packet["doctrine_sources"])
        search_mode = packet["search_mode"]
    else:
        query = " ".join(x for x in [data.topic, data.details] if x).strip()
        search_mode = "문자검색"
        passages = search_passages(query, limit=32)
        word_notes = []
        doctrine_notes = []
        packet = None
        if data.use_rag and data.embedding_model and data.embedding_model in rag_stats()["models"]:
            try:
                passages = hybrid_search(query, client, data.embedding_model, limit=32)
                search_mode = "하이브리드 RAG"
            except (ConnectionError, RuntimeError, ValueError):
                search_mode = "문자검색(자동 복귀)"
        if data.use_rag and data.embedding_model and data.embedding_model in rag_stats()["doctrine_models"]:
            try:
                denomination_code = data.denomination_code.strip()
                doctrine_notes = (search_approved_doctrine(query, client, data.embedding_model, denomination_code, DB_PATH, limit=6, include_common=True)
                    if denomination_code else doctrine_search(query, data.tradition, client, data.embedding_model, limit=6))
            except (ConnectionError, RuntimeError, ValueError):
                doctrine_notes = []
    clean_outline = None
    web_evidence = []
    web_grounding_meta = {"enabled": False, "provider_available": False, "results": 0, "fallback": False}
    if data.web_grounding and web_grounding_enabled() and should_search_web(f"{data.topic} {data.details}"):
        web_query = build_web_query(data.topic, data.details)
        web_evidence, web_grounding_meta = WebEvidenceAdapter(HttpJsonWebSearchProvider()).search(web_query)
    if data.outline:
        for reference in outline_references(data.outline):
            for item in compare_reference(reference):
                if not any(p.get("translation") == item.get("translation") and p.get("reference") == item.get("reference") for p in passages):
                    passages.append(item)
        try:
            clean_outline = validate_sermon_outline(data.outline, passages)
        except ValueError as exc:
            raise HTTPException(400, f"설교 구조 근거 검증 실패: {exc}") from exc
    if packet is not None:
        packet["bible_sources"] = list(passages)
        packet["counts"]["bible_sources"] = len(passages)
    try:
        result = generate_sermon_workflow(
            data,
            client=client,
            passages=passages,
            word_notes=word_notes,
            doctrine_notes=doctrine_notes,
            web_evidence=web_evidence,
            web_grounding_meta=web_grounding_meta,
            search_mode=search_mode,
            reading_cpm=reading_cpm,
            clean_outline=clean_outline,
            select_generation_model=lambda provider, requested: _select_generation_model(provider, requested, data.minutes),
        )
    except (ConnectionError, RuntimeError) as exc:
        raise HTTPException(503, str(exc)) from exc
    finally:
        client.end_generation()
    result["research_packet"] = packet
    return result


@app.post("/api/sermons/cancel")
def cancel_sermon_generation(request: Request):
    generation_id = request.headers.get("X-Generation-Id", "").strip()
    if not generation_id:
        raise HTTPException(400, "취소할 생성 작업 ID가 없습니다.")
    return {"ok": cancel_generation(generation_id), "generation_id": generation_id}


@app.post("/api/sermons/save")
def save_sermon_version(data: SermonSaveRequest):
    try:
        return {"ok": True, **save_sermon(data.topic, data.content, data.metadata, data.sermon_id)}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/sermons/saved")
def saved_sermons():
    return {"items": list_sermons()}


@app.get("/api/sermons/{sermon_id}/versions")
def saved_versions(sermon_id: int):
    return {"sermon_id": sermon_id, "items": sermon_versions(sermon_id)}


@app.get("/api/sermons/{sermon_id}/diff")
def version_diff(sermon_id: int, a: int, b: int):
    try:
        return {"sermon_id": sermon_id, "a": a, "b": b, "diff": compare_sermon_versions(sermon_id, a, b)}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/audits/{audit_id}")
def generation_audit(audit_id: int):
    audit = get_generation_audit(audit_id)
    if not audit:
        raise HTTPException(404, "감사 기록을 찾을 수 없습니다.")
    return audit


@app.get("/api/sermons/{sermon_id}/versions/{version}/reviews")
def version_reviews(sermon_id: int, version: int):
    versions = {item["version"] for item in sermon_versions(sermon_id)}
    if version not in versions:
        raise HTTPException(404, "설교 버전을 찾을 수 없습니다.")
    return sermon_review_state(sermon_id, version)


@app.post("/api/sermons/{sermon_id}/versions/{version}/reviews")
def create_version_review(sermon_id: int, version: int, data: SermonReviewRequest):
    try:
        review = add_sermon_review(sermon_id, version, data.reviewer, data.status, data.comment)
        return {"ok": True, "review": review, **sermon_review_state(sermon_id, version)}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/sermons/{sermon_id}/versions/{version}/reaudit")
def reaudit_version(sermon_id: int, version: int):
    try:
        audit = reaudit_sermon_version(sermon_id, version)
        return {"ok": True, "audit": audit, "citation_analysis": audit.get("citation_analysis", {}),
                "post_generation_quality": audit.get("post_generation_quality", {})}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/sermons/{sermon_id}/versions/{version}/lock")
def lock_version(sermon_id: int, version: int, data: SermonLockRequest):
    try:
        lock = lock_sermon_version(sermon_id, version, data.locked_by)
        return {"ok": True, "lock": lock, **sermon_review_state(sermon_id, version)}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/sermons/{sermon_id}/versions/{version}/revision-suggestions")
def list_revision_suggestions(sermon_id: int, version: int):
    versions = {item["version"] for item in sermon_versions(sermon_id)}
    if version not in versions:
        raise HTTPException(404, "설교 버전을 찾을 수 없습니다.")
    return {"items": revision_suggestions(sermon_id, version)}


@app.post("/api/sermons/{sermon_id}/versions/{version}/revision-suggestions")
def create_revision_suggestions(sermon_id: int, version: int, data: RevisionSuggestionRequest):
    client = LMStudioClient()
    try:
        model, _ = _select_generation_model(client, data.model)
        result = generate_revision_suggestions(sermon_id, version, client, model)
        return {"ok": True, "model": model, **result}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ConnectionError, RuntimeError) as exc:
        raise HTTPException(503, f"LM Studio 수정 제안 생성 실패: {exc}") from exc


@app.post("/api/sermons/{sermon_id}/versions/{version}/apply-revisions")
def apply_revisions(sermon_id: int, version: int, data: RevisionApplyRequest):
    try:
        return {"ok": True, **apply_revision_suggestions(sermon_id, version, data.suggestion_ids)}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/sermons/{sermon_id}/versions/{version}/export-package")
def export_final_package(sermon_id: int, version: int):
    version_item = next((item for item in sermon_versions(sermon_id) if item["version"] == version), None)
    if not version_item:
        raise HTTPException(404, "최종 패키지로 만들 설교 버전을 찾을 수 없습니다.")
    state = sermon_review_state(sermon_id, version)
    if not state.get("locked") or not (state.get("lock") or {}).get("integrity_ok"):
        raise HTTPException(409, "무결성이 확인된 최종 잠금 승인본만 패키지로 출력할 수 있습니다.")
    meta = dict(version_item.get("metadata") or {})
    meta["audit"] = state.get("audit")
    meta["audit_id"] = (state.get("audit") or {}).get("id")
    meta["citation_analysis"] = (state.get("audit") or {}).get("citation_analysis", {})
    meta["post_generation_quality"] = (state.get("audit") or {}).get("post_generation_quality", {})
    meta["review_state"] = state
    reading_cpm = int(meta.get("reading_cpm") or get_reading_cpm())
    meta["reading_cpm"] = reading_cpm
    meta["minutes_estimate"] = estimate_minutes(version_item["content"], reading_cpm)
    if not meta.get("topic"):
        meta["topic"] = next((item["topic"] for item in list_sermons() if item["id"] == sermon_id), "설교문")
    sources = meta.get("sources", []) if isinstance(meta.get("sources", []), list) else []
    project = get_project_meta(sermon_id)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = EXPORTS / f"sermon_final_{sermon_id}_v{version}_{stamp}.zip"
    try:
        manifest = write_final_package(path, sermon=version_item["content"], meta=meta, sources=sources, project=project)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"filename": path.name, "url": f"/downloads/{path.name}", "manifest": manifest}


@app.post("/api/sermons/{sermon_id}/versions/{version}/export-hwpx")
def export_final_hwpx(sermon_id: int, version: int):
    """Export only an approved, integrity-checked final version as HWPX."""
    version_item = next((item for item in sermon_versions(sermon_id) if item["version"] == version), None)
    if not version_item:
        raise HTTPException(404, "HWPX로 만들 설교 버전을 찾을 수 없습니다.")
    state = sermon_review_state(sermon_id, version)
    if not state.get("locked") or not (state.get("lock") or {}).get("integrity_ok"):
        raise HTTPException(409, "무결성이 확인된 최종 잠금 승인본만 HWPX로 출력할 수 있습니다.")
    meta = dict(version_item.get("metadata") or {})
    meta["audit"] = state.get("audit")
    meta["review_state"] = state
    meta["topic"] = meta.get("topic") or next((item["topic"] for item in list_sermons() if item["id"] == sermon_id), "설교문")
    reading_cpm = int(meta.get("reading_cpm") or get_reading_cpm())
    meta["reading_cpm"] = reading_cpm
    meta["minutes_estimate"] = estimate_minutes(version_item["content"], reading_cpm)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = EXPORTS / f"sermon_final_{sermon_id}_v{version}_{stamp}.hwpx"
    try:
        write_hwpx(path, sermon=version_item["content"], meta=meta)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"filename": path.name, "url": f"/downloads/{path.name}", "format": "hwpx", "version": version}


def export_markdown(data: dict):
    text = str(data.get("text", "")).strip()
    if not text:
        raise HTTPException(400, "내보낼 설교문이 없습니다.")
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = EXPORTS / f"sermon_{stamp}.md"
    path.write_text(sermon_with_media_prompts(text, meta), encoding="utf-8")
    return {"filename": path.name, "url": f"/downloads/{path.name}"}


def export_html(data: dict):
    text = str(data.get("text", "")).strip()
    if not text:
        raise HTTPException(400, "내보낼 설교문이 없습니다.")
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    sources = data.get("sources") if isinstance(data.get("sources"), list) else []
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = EXPORTS / f"sermon_dashboard_{stamp}.html"
    path.write_text(dashboard_html(sermon=text, meta=meta, sources=sources), encoding="utf-8")
    return {"filename": path.name, "url": f"/downloads/{path.name}"}


def export_word(data: dict):
    text = str(data.get("text", "")).strip()
    if not text:
        raise HTTPException(400, "내보낼 설교문이 없습니다.")
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = EXPORTS / f"sermon_{stamp}.docx"
    try:
        write_docx(path, sermon=text, meta=meta)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"filename": path.name, "url": f"/downloads/{path.name}"}


def export_pdf(data: dict):
    text = str(data.get("text", "")).strip()
    if not text:
        raise HTTPException(400, "내보낼 설교문이 없습니다.")
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    sources = data.get("sources") if isinstance(data.get("sources"), list) else []
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = EXPORTS / f"sermon_{stamp}.pdf"
    try:
        write_pdf(path, sermon=text, meta=meta, sources=sources)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"filename": path.name, "url": f"/downloads/{path.name}"}


def export_grounding(data: dict):
    if os.getenv("GROUNDING_REPORT_EXPORT_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(404, "Grounding 검토 보고서 Export가 비활성화되어 있습니다.")
    report = build_grounding_report_data(data)
    fmt = str(data.get("format", "html")).strip().lower()
    if fmt not in {"html", "markdown", "md"}:
        raise HTTPException(400, "지원하는 보고서 형식은 html 또는 markdown입니다.")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = safe_report_stem(report.title, stamp)
    suffix, content = (("md", render_grounding_markdown(report)) if fmt in {"markdown", "md"} else ("html", render_grounding_html(report)))
    path = EXPORTS / f"{stem}.{suffix}"
    path.write_text(content, encoding="utf-8")
    return {"filename": path.name, "url": f"/downloads/{path.name}", "format": suffix}


def download(filename: str):
    safe = Path(filename).name
    path = EXPORTS / safe
    if not path.exists():
        raise HTTPException(404, "파일을 찾을 수 없습니다.")
    return FileResponse(path, filename=safe)
