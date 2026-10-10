# Gate 1 Research Schema Baseline

## 기준

- 확인일: 2026-10-02
- 제품 버전: `40.9.13`
- Git 브랜치: `refactor/phase1-baseline-20260905`
- 작업 트리: 기존 수정 및 미추적 파일이 존재함
- 기준 테스트: `517 passed, 19 skipped, 0 failed`
- 실행 시간: `90.86s`

## 변경 전 보호 대상

- 기존 7단계 설교 Workflow
- SQLite 기본 저장소
- LM Studio localhost 연결과 streaming generation
- 성경 본문 존재·범위 검증
- 원어와 번역 자료의 출처 구분
- 기존 Evidence/Audit, 목회자 승인, 최종 잠금
- 기존 Markdown, HTML, PDF, DOCX, HWPX 출력
- 기존 RAG 기본 전략과 선택형 FTS5/RRF

## Gate 1 허용 범위

- 비영속 데이터 계약 보완
- 신규 Schema 초안 정의
- Section 상태 및 버전 규칙 정의
- Snapshot 계약 정의
- 기존 데이터와 신규 계약의 매핑 문서화
- 계약 단위 테스트

## Gate 1 금지 범위

- 운영 DB migration 실행
- 기존 테이블 변경 또는 삭제
- 신규 Router 및 UI 연결
- 실제 LM Studio Section Builder 실행
- RAG 기본 전략 변경
- 기존 승인·잠금·출력 경로 교체

## 변경 파일 기록

Gate 1에서 새로 추가하거나 직접 수정한 파일만 이 목록에 기록한다.

- `docs/audit/gate1-research-schema-baseline-2026-10-02.md`
- `docs/audit/gate1-research-schema-design-2026-10-02.md`
- `app/application/research_persistence_contracts.py`
- `tests/test_research_persistence_contracts.py`
- `app/application/canary_builders.py`
- `tests/test_canary_builders.py`
- `reports/GATE1_GATE2A_RESEARCH_CANARY_REPORT_2026-10-02.md`
- `app/migrations.py`
- `app/repositories/research_sections.py`
- `tests/test_research_sections_migration.py`
- `tests/test_research_sections_repository.py`
- `reports/GATE2B_RESEARCH_SECTION_PERSISTENCE_REPORT_2026-10-02.md`
- `app/application/research_section_service.py`
- `tests/test_research_section_service.py`
- `reports/GATE2C_RESEARCH_SECTION_SERVICE_REPORT_2026-10-02.md`
- `app/routers/research.py`
- `tests/test_research_router.py`
- `reports/GATE2D_RESEARCH_ROUTER_CONTRACT_REPORT_2026-10-02.md`
- `scripts/rehearse_research_sections.py`
- `tests/test_research_router_wiring.py`
- `app/main.py` (Research Router wiring only; existing user changes preserved)
- `reports/GATE2E_RESEARCH_ROUTER_WIRING_REPORT_2026-10-02.md`
- `scripts/activate_research_sections.py`
- `tests/test_research_sections_activation.py`
- `reports/GATE2F_RESEARCH_SCHEMA_ACTIVATION_REPORT_2026-10-02.md`
- `backups/sermon_backup_20261002_110640_572809.zip` (검증된 운영 DB 백업)
- `data/bible.db` (Gate 2F additive migration: `sermon_sections`)
- `scripts/smoke_research_http.py`
- `tests/test_research_http_smoke_contract.py`
- `reports/GATE2G_RESEARCH_HTTP_SMOKE_REPORT_2026-10-02.md`
- Gate 2H files: `app/routers/research.py`, `tests/test_research_router.py`
- `reports/GATE2H_RESEARCH_CANARY_GUARDRAILS_REPORT_2026-10-02.md`

## Gate 1 검증 결과

- 관련 계약 테스트: `11 passed`
- 전체 테스트: `520 passed, 19 skipped, 0 failed`
- 운영 DB migration: 실행하지 않음
- 판정: Gate 1 통과

## Gate 2A 검증 결과

- 관련 테스트: `11 passed`
- 전체 테스트: `523 passed, 19 skipped, 0 failed`
- 운영 DB 및 기존 Schema 변경: 없음
- 판정: `structure` adapter Canary 통과

## Gate 2B 검증 결과

- 관련 테스트: `12 passed`
- 전체 테스트: `529 passed, 19 skipped, 0 failed`
- 운영 DB migration: 실행하지 않음
- 판정: Section migration·Repository Canary 통과

## Gate 2C 검증 결과

- 관련 통합 테스트: `16 passed`
- 전체 테스트: `533 passed, 19 skipped, 0 failed`
- 자동 수정: citation coverage 사전검증으로 잘못된 요청의 Builder 실행 방지
- 운영 DB 및 runtime 연결: 없음
- 판정: Section application service Canary 통과

## Gate 2D 검증 결과

- 관련 Router 테스트: `24 passed`
- 전체 테스트: `540 passed, 19 skipped, 0 failed`
- 자동 수정: 추가 패키지 설치 없이 Router endpoint 직접 호출 방식으로 환경 호환성 복구
- 운영 Router 등록 및 DB migration: 없음
- 판정: feature-gated Research Router 계약 통과

## Gate 2E 검증 결과

- 실제 운영 DB read-only 복제 rehearsal: 통과
- 원본 DB 변경: 없음
- 핵심 row count 및 기존 Schema hash: 보존
- 복제본 quick check: `ok`
- 관련·인증·Router 테스트: `38 passed`
- 전체 테스트: `544 passed, 19 skipped, 0 failed`
- 자동 수정: readiness 선검사, script import 경로, OpenAPI 기반 route 검사
- 운영 DB migration: 실행하지 않음
- 판정: Feature flag OFF Router wiring 통과

## Gate 2F 검증 결과

- 운영 백업: 생성 및 SHA-256·quick check 검증 완료
- 운영 migration: `sermon_research_sections_canary_v1` 적용 완료
- 재실행: idempotent no-op 확인
- 기존 핵심 row count: 전부 보존
- 적용 후 quick check: `ok`
- 관련 테스트: `16 passed`
- 전체 테스트: `547 passed, 19 skipped, 0 failed`
- Feature flag: OFF 유지
- 판정: 운영 Schema activation 통과, 기능은 비활성 상태

## Gate 2G 검증 결과

- 격리 localhost Uvicorn HTTP smoke: 통과
- 비로그인 401, 로그인 flag OFF 503: 통과
- 격리 flag ON structure v1·재시도 v2: 통과
- 중심 본문 부재 차단: 통과
- 관련 테스트: `17 passed`
- 전체 테스트: `548 passed, 19 skipped, 0 failed`
- 운영 Feature flag 및 운영 Section 데이터: 변경 없음
- 판정: HTTP Canary 계약 통과

## Gate 2H 검증 결과

- 관리자 실행 경계: 통과
- dry-run 및 명시적 target confirmation: 통과
- 일반 사용자 차단: 통과
- 프로젝트·본문 불일치 차단: 통과
- 격리 HTTP smoke: `ok=true`
- 관련 테스트: `18 passed`
- 전체 테스트: `551 passed, 19 skipped, 0 failed`
- 운영 Feature flag: OFF 유지
- 운영 Section 데이터: 추가 없음
- 판정: Canary 운영 guardrail 통과

## 경고

- 현재 작업 트리의 기존 변경은 이번 Gate의 변경으로 간주하지 않는다.
- 기존 변경 파일을 reset, checkout, 삭제 또는 덮어쓰지 않는다.
- 이후 기준선이 `517 passed, 19 skipped`보다 나빠지면 다음 Gate로 진행하지 않는다.
