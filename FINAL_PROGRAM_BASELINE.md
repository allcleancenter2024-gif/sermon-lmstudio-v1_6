# Final Program Baseline · V40.9.15

기준일: 2026-10-11  
공식 제품 버전: **40.9.15**  
제품 버전의 유일한 원본: `VERSION.txt`  
공식 소스 작업 폴더: `sermon-lmstudio-v1_6` 프로젝트 루트  
Windows 실행 파일: `release/V40.9.15/SermonLMStudio_V40.9.15.exe`  
권장 실행 배치: `release/V40.9.15/RUN_SermonLMStudio.bat`

## 1. 기준 프로그램 정책

- 향후 코드 변경은 이 프로젝트 루트의 소스를 기준으로 합니다.
- 앱, launcher, API, UI, 빌드 설정은 `app.version.APP_VERSION`과 `VERSION.txt`를 공유합니다. 새 버전을 낼 때 소스 곳곳에 숫자를 복제하지 않습니다.
- `release/V40.9.15/`는 해당 소스로 만든 최종 Windows 산출물입니다. `dist/`의 이전 실행 파일들은 보존된 구버전 산출물이며 현재 기준으로 실행·수정하지 않습니다.
- 권장 BAT는 `SERMON_USER_ROOT`를 프로젝트 루트로 설정해 현재 SQLite DB, 백업, 내보내기, 원어 자료를 계속 사용합니다. 사용자 DB를 EXE에 복사하지 않았습니다.
- EXE를 프로젝트 밖으로 복사해서 직접 실행하면 앱 기본 동작에 따라 사용자 데이터 경로가 `%LOCALAPPDATA%\SermonLMStudio`가 됩니다. 현재 프로젝트 데이터를 사용할 때는 권장 BAT로 실행하십시오.
- 2026-10-11 보완 작업 시작 시 Git 작업 트리에는 261개의 변경 또는 미추적 경로가 있었습니다. 기존 작업을 보존했고 새 커밋이나 태그를 만들지 않았습니다. 향후 정리/커밋 시 기존 변경 소유자를 먼저 확인하십시오.

## 2. 프로그램 챕터 지도

| 챕터 | 책임 | 기준 경로 |
|---|---|---|
| 1. 실행과 설정 | 제품 버전, 경로, Windows 시작, 앱 조립 | `VERSION.txt`, `app/version.py`, `app/config.py`, `app/paths.py`, `launcher.py`, `app/main.py` |
| 2. 화면 | 설교 작성 UI, 스타일, 동작, 정적 리소스 | `templates/`, `static/` |
| 3. API 경계 | 기능별 FastAPI 라우터 | `app/routers/` |
| 4. 업무 흐름 | 프로젝트·설정 facade, job, 설교 생성 서비스 | `app/application/`, `app/services/` |
| 5. 설교와 근거 | 프롬프트, 본문 검증, evidence packet, citation trace, audit | `app/prompts/`, `app/evidence/`, `app/grounding/`, `app/services/sermon_service.py` |
| 6. AI 공급자 | 로컬 LM Studio 및 선택적 web evidence provider | `app/providers/`, `app/lmstudio_control.py` |
| 7. 저장소와 DB | SQLite schema·migration, 성경/설교/교리/설정 repository | `app/repositories/`, `app/migrations.py`, `app/core.py`(호환 facade 포함) |
| 8. 검색 | lexical FTS5, semantic, hybrid fusion, 품질 측정 | `app/rag/` |
| 9. 원어와 자료 처리 | 성경 import, 원어·형태론, 정렬, 문서 export | `app/importers.py`, `app/morphgnt.py`, `app/alignment.py`, `app/exporters.py`, `app/assets/hwpx_base/` |
| 10. 검증과 운영 | 자동 테스트, Windows build, 복구와 설치 안내 | `tests/`, `build_windows.bat`, `start.bat`, `scripts/`, `docs/` |
| 11. 사용자 데이터 | SQLite, 원어/성경 소스, 백업, export, 폰트 | `data/`, `backups/`, `exports/`, `fonts/` |

## 3. 단일 버전 및 새 릴리스 절차

1. `VERSION.txt`의 patch 버전을 한 번만 갱신합니다.
2. 버전 계약 테스트와 전체 테스트를 실행합니다. 기준선은 2026-10-11 기준 **599 passed, 19 skipped**입니다. 같은 통합 조건에서 pass 수가 낮아지면 릴리스하지 않습니다.
3. `build_windows.bat`를 실행합니다. 빌더는 compile, 전체 pytest, PDF/한글 폰트 준비 상태, EXE의 `--version`을 검증합니다.
4. 산출물은 `release/V<버전>/`에 둡니다. 기존 `dist/` 산출물은 덮어쓰거나 삭제하지 않습니다.
5. `RUN_SermonLMStudio.bat`로 EXE를 실행하고 필요한 경우 `--diagnose`를 사용해 LM Studio 로컬 상태를 확인합니다.
6. 보고서와 baseline 기록을 함께 남깁니다. 데이터베이스 schema/사용자 데이터 변경은 별도 백업·migration 계획과 테스트 없이는 하지 않습니다.

## 4. 안정성 원칙

- LM Studio 기본 주소는 localhost `http://127.0.0.1:12345/v1`를 유지합니다.
- 중심 본문·인용·Evidence Packet·원어 자료의 출처 검증을 완화하지 않습니다.
- 사용자 DB, 원어 source, backups, exports를 릴리스 빌드에 복사하거나 정리하지 않습니다.
- 기존 라우트·요청/응답 형식과 기존 generation behavior를 회귀 검증 없이 바꾸지 않습니다.
- `app/core.py`와 `app/main.py`를 한 번에 재작성하지 않습니다. 모듈 이동은 테스트를 통과하는 작은 단계로 합니다.

## 5. V40.9.15 범위

- `VERSION.txt`를 공식 제품 버전 40.9.15로 올리고 runtime version 계약을 단일 원본에 맞췄습니다.
- 오래된 V40 launcher의 고정 버전을 제거해 `VERSION.txt`를 읽게 했습니다.
- 작업 요약 export의 파일 이름에서 오래된 버전 숫자를 제거하고 화면의 runtime version을 사용합니다.
- PyInstaller 산출 경로를 버전별 `release/V<버전>/`로 분리하고 HWPX base template를 함께 포함시킵니다.
- 설교 생성에서 웹 evidence를 반복 `as_dict()` 변환하지 않도록 재사용하는 최적화를 포함합니다.
- SQLite schema와 기존 데이터는 바꾸지 않았습니다.


## 6. 2026-10-11 기능 보강 UI 정리

- 최근 구현되어 있던 초기 관리자 계정 생성, 별도 계정 DB, Research Canary, 협업 배정·revision 검토 기능을 작업 종합 대시보드에 추가로 요약합니다.
- 상세 기능은 기존 로그인, 본문 연구, 저장·검토 패널에 그대로 둡니다. 새 메뉴나 입력 흐름은 만들지 않아 설교 작성 화면의 기본 배치를 바꾸지 않습니다.
- Canary는 feature flag로 비활성화될 수 있고 현재 지원 범위는 structure Section입니다. 상태는 읽기 전용, 사전 점검은 관리자 dry-run/approval-check로 구분합니다.
- 협업은 로컬 계정과 사용자 역할에 한정됩니다. 외부 말씀길 서비스 연동은 API·인증·소유권 계약이 확인되기 전까지 제공하지 않습니다.
- 이 보강은 문구·현황 표시 범위이며 SQLite 성경/설교 데이터, schema, 기존 경로와 생성 동작은 변경하지 않습니다.
- 레이아웃은 기존 2열 대시보드 그리드에 카드 하나를 더해 2x2 구조로 맞추고, 좁은 화면에서는 기존 media query대로 1열로 접습니다.
