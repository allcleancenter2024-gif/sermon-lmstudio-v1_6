# app/core.py Dependency Map

## 범위와 표기

- 현재 위치는 모두 `app/core.py`이다.
- 호출 파일은 정적 import 및 주요 직접 사용처다. `main`은 `app/main.py`, `tests`는 `tests/*`를 뜻한다.
- DB는 SQLite `bible.db`/주입 `db_path` 의존, LM은 `LMStudioClient` 의존이다.
- 위험도는 **낮음**(순수/독립)·**중간**(공개 API/다른 core 함수)·**높음**(SQLite schema 또는 도메인 흐름)·**매우 높음**(여러 경계 결합)이다.

|카테고리|함수/클래스|호출 파일 / 호출되는 함수|DB|LM|위험|권장 목적지|
|---|---|---|---:|---:|---|---|
|CONFIG|`DB_PATH`, `SUPPORTED_SERMON_MINUTES`, `DEFAULT_SERMON_MINUTES`, `DEFAULT_LMSTUDIO_URL`, `LEGACY_LMSTUDIO_URL`|main, tests / 없음|DB_PATH만 예|아니오|낮음|`app/core/constants.py` (DB_PATH는 config에서 계산)|
|CONFIG|`normalize_lmstudio_url`, `get_lmstudio_url`, `set_lmstudio_url`|main, LM client, tests / `app.repositories.settings`|예|URL 설정|분리 완료|`app/config.py`|
|CONFIG|`get_reading_cpm`, `set_reading_cpm`, `calibrate_reading_cpm`|main / `app.repositories.settings`|예|아니오|분리 완료|`app/repositories/settings.py` (core re-export)|
|DATABASE|`init_db`는 core 유지; `delete_bible_translation`, `db_stats`, `fetch_bible_integrity_metrics`, `fetch_bible_dashboard_rows`는 `app.repositories.bible`로 분리 완료, dashboard/integrity facade 조립은 core 유지|main, tests / SQLite 직접·RAG·license|예|아니오|부분 분리|`app/repositories/bible.py`|
|BIBLE|`register_translation_license`, `translation_licenses`, `add_passage`, `persist_passage_batch`, `delete_bible_translation`, `search_passages`, `compare_reference`는 `app.repositories.bible`로 분리 완료 (core re-export); import normalization/license 정책과 research는 core 유지|main, tests / SQLite, references, RAG invalidation, 정책 함수|예|선택 RAG 호출|부분 분리|`app/repositories/bible.py`|
|ORIGINAL_LANGUAGE|`add_original_note`, `original_lexicon_stats`, `fetch_original_note_rows`는 `app.repositories.bible`로 분리 완료; `original_notes` public facade는 core에 유지하며 enrichment 수행|main, tests / SQLite, references|예|아니오|부분 분리|`app/repositories/bible.py`|
|DOCTRINE|`add_doctrine_chunk`, `fetch_doctrine_chunks`, `persist_doctrine_embeddings`, `fetch_doctrine_vector_rows`는 `app.repositories.doctrine`로 분리 완료; `build_doctrine_index`의 Provider·packing과 `doctrine_search`의 Provider·scoring은 core 유지|main, tests / SQLite, client embedding|예|일부|부분 분리|`app/repositories/doctrine.py`|
|PROJECT|`get_project_meta`, `update_project_meta`, `list_sermons`, `sermon_versions`, `compare_sermon_versions`, `fetch_project_dashboard_inputs`는 `app.repositories.project`에 유지; `persist_sermon_version`는 Sermon Repository 구현의 compatibility re-export만 유지; `project_dashboard` facade의 workflow state·응답 조립과 public `save_sermon` facade는 core 유지|main, tests / SQLite·JSON metadata·audit/review|예|아니오|부분 분리|`app/repositories/project.py` (compat), `app/repositories/sermon.py`|
|SERMON|`persist_sermon_version` DB persistence는 `app.repositories.sermon`; 생성 후처리 orchestration(`generate_sermon_workflow`)는 `app.services.sermon_service`; `sermon_time_plan`, `compact_outline_study`, `validate_sermon_outline`, `outline_references`, `_parse_json_response`, `generate_revision_suggestions`, `apply_revision_suggestions`, `estimate_minutes`는 기존 모듈 유지|main, tests / research, prompts, SQLite, client|부분|일부|중간|후속 Sermon Service 확장, `sermon/outline.py`, `generator.py`|
|LMSTUDIO|`app.providers.lmstudio.LMStudioClient` (URL/요청/model catalog/retry/SSE/chat/embed/probe); `app.core.LMStudioClient` compatibility adapter|main, tests, RAG, doctrine, sermon / `app.config`, `loaded_model_ids`, urllib|설정 읽기|예|분리 완료|`app/providers/lmstudio.py`|
|RAG|`rag_stats`, `fetch_rag_vector_rows`, `fetch_rag_passages`, `persist_rag_embeddings`는 `app.repositories.rag`; `cosine_similarity`, `restore_rag_vector`, `score_semantic_vector`, `semantic_search`는 `app.rag.semantic`; `fuse_hybrid_results`, `rrf_fusion`, `filter_related_candidates`, `hybrid_search`는 `app.rag.hybrid`; 선택적 FTS5 lexical은 `app.rag.fts` (`RAG_LEXICAL_STRATEGY`, 기본 legacy); fusion은 `RAG_FUSION_STRATEGY` (`legacy_weighted` 기본); `pack_rag_vector`, `build_rag_index`, `recommend_related`는 core 유지|main, tests / SQLite, `rag_fts`, client embedding, `search_passages`|예|예|부분 분리|후속 FTS sync, RAG orchestration 전체 분석 또는 Router 단계|
|PROMPT|`build_outline_prompt`, `_round_robin_references`, `build_grounding`, `build_sermon_prompt`, `build_resize_prompt`, `build_translation_policy_prompt`, `build_social_context_policy_prompt`, `build_interpretation_flow_prompt`|main, tests / policy helpers|아니오|아니오|중간|후속 `prompts/*`|
|QUALITY|`analyze_citations`, `analyze_social_neutrality`, `build_post_generation_quality`, `validate_quotes`|main, tests / prompt policy + Bible evidence|부분|아니오|높음|후속 `sermon/quality.py`|
|AUDIT|`create_generation_audit`, `get_generation_audit`, `audit_for_version`, `reaudit_sermon_version`, `sermon_version_lock`, `lock_sermon_version`, `add_sermon_review`, `sermon_review_history`, `sermon_review_state`, `sermon_workflow_status`, `revision_suggestions`|main, tests / SQLite + quality + project|예|아니오|매우 높음|후속 `sermon/audit.py`|
|UTILITY|`build_social_context_policy`, constants `INTERPRETATION_FLOW_DEFINITION`, `ENGLISH_TRANSLATION_POLICY`, regex 정책 상수, translation helpers (`_translation_token`~`sort_interpretation_passages`), `build_translation_policy`, `build_interpretation_flow`|main, tests, prompt/quality/research / pure helpers|아니오|아니오|중간|상수는 `constants.py`; 나머지는 후속 policy 모듈|

## 현재 모듈 그래프

```text
app.main
  ├─ app.core ─┬─ app.config ─┬─ app.repositories.settings ─┬─ app.paths
  │            │              └─ app.constants               └─ SQLite
  │            ├─ app.repositories.settings
  │            ├─ app.repositories.bible ─┬─ app.paths
  │            │                          └─ SQLite (passages/license/RAG invalidation)
  │            ├─ app.providers.lmstudio ─┬─ app.config
  │            │                          └─ app.lmstudio_control (loaded_model_ids)
  │            ├─ app.references
  │            └─ SQLite
  ├─ app.backup / app.exporters / app.importers / app.notebooklm
  └─ app.lmstudio_control (server start/diagnostics)

tests ──patch/import──> app.core and app.main
```

## 예상 Import Cycle 및 방지 규칙

|예상 cycle|발생 방식|방지 규칙|
|---|---|---|
|`core facade → config → core`|새 config가 `init_db`/`DB_PATH`를 core에서 import|config는 `paths`·표준 라이브러리만 import; settings DB 함수는 config가 아니라 후속 repository에 둔다.|
|`core facade → provider → core`|provider가 기존 URL helper를 core에서 import|provider는 `config.normalize_lmstudio_url`/`get_lmstudio_url`만 사용; core re-export는 한 방향이다.|
|`rag → provider → rag`|provider가 embedding/RAG를 직접 안다면 발생|provider는 HTTP transport/model catalog/chat/embed만 소유; RAG는 client protocol/객체를 인자로 받는다.|
|`sermon → rag → sermon`|RAG가 evidence packet 또는 prompt를 import|RAG는 passage 결과만 반환, sermon은 orchestration만 수행한다.|
|`repositories → sermon → repositories`|repository가 workflow/quality 정책을 호출|repository는 CRUD/SQL만, 도메인 서비스가 repository를 호출한다.|

## Phase 1A/1B 호환 전략

1. `app/core.py`는 당분간 **compatibility facade**로 유지한다.
2. 새 모듈은 기존 `core.py`를 import하지 않는다; 의존 방향은 `core facade → new module`이다.
3. `main.py`와 테스트의 import/patch 대상은 Phase 1 동안 변경하지 않는다.
4. `LMStudioClient` type annotation이 필요한 기존 함수는 구현 이동 후 facade re-export로 이름을 계속 제공한다.
