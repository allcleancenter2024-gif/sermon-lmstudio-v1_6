# Sermon LM Studio 리팩터링·Grounding 작업 종합 대시보드

작성일: 2026-09-01  
제품 버전: V40.9.1  
현재 상태: 안정화 기준선 유지 / 다음 단계 승인 대기

## 1. 전체 요약

현재까지 작업은 `core.py` 중심 구조에서 Repository·Service·RAG·Evidence·Grounding·Router 계층으로 점진적으로 분리하는 방식으로 진행되었다. 각 단계마다 기존 API·SQLite schema·응답 형식을 우선 보존했으며, Web Grounding은 선택형·기본 비활성 상태로 추가했다.

핵심 원칙은 다음과 같다.

- Scripture Evidence > Web Evidence
- Web Evidence는 항상 Tier D
- 기존 SQLite schema와 데이터 유지
- Web Search 실패 시 내부 Evidence Pipeline으로 fallback
- 실제 Provider·Multi-Provider·자동 재생성은 승인 전 실행하지 않음

## 2. 단계별 진행 현황

| 단계 | 내용 | 상태 | 결과 |
|---|---|---:|---|
| Phase 0 | Baseline·의존성 지도·안전 경계 | 완료 | 기존 구조 및 변경 금지 영역 확인 |
| Phase 1C-1 | Settings Repository 분리 | 완료 | `app/repositories/settings.py` |
| Phase 1C-2 | Project Repository 분리 | 완료 | `app/repositories/project.py` |
| Phase 1C-3 | Doctrine Repository 분리 | 완료 | `app/repositories/doctrine.py` |
| Phase 1C-4 | Bible Repository 분리 | 완료 | `app/repositories/bible.py` |
| Phase 1C-5 | Sermon Repository 분리 | 완료 | `app/repositories/sermon.py` |
| Phase 1D | Sermon Service 분리 | 완료 | `app/services/sermon_service.py` |
| Phase 1E | RAG 모듈화 | 완료 | semantic/hybrid/FTS 모듈 |
| Phase 2A | SQLite FTS5 선택 도입 | 완료 | 기본 legacy 유지, 선택 flag |
| Phase 2B | RRF Hybrid RAG 선택 도입 | 완료 | 기본 legacy weighted 유지 |
| Phase 2C | Evidence 정규화·Validator | 완료 | 공통 EvidenceCandidate 및 Tier 정책 |
| Phase 2D | Grounding Audit | 완료 | Claim 추출·Evidence 연결 |
| Phase 2E | Grounding Dashboard | 완료 | 기본 비활성 read-only 표시 |
| Phase 2F | Grounding Report Export | 완료 | HTML/Markdown 선택 export |
| Phase 3A | main.py Router 분리 | 완료 | health/settings/projects/doctrine/bible/exports |
| Phase 3B | 선택형 Web Grounding Adapter | 완료 | 기본 OFF, runtime Tier D |
| Phase 3C | Web Provider Evaluation Gate | 완료 | 30 query mock 평가, live 평가 보류 |

## 3. 현재 아키텍처

```text
FastAPI main.py
  ├─ Routers: health / settings / projects / doctrine / bible / exports
  ├─ Services: sermon_service
  ├─ Repositories: settings / project / doctrine / bible / sermon / rag
  ├─ RAG: semantic / hybrid / fts
  ├─ Evidence: normalize / EvidenceCandidate
  ├─ Grounding: Validator / Audit
  ├─ Providers: lmstudio / optional web
  └─ Exporters: sermon / grounding report
```

의존 방향은 Router/Service → Repository·RAG·Provider·Grounding으로 단방향을 유지하며 Repository/Provider가 `app.main`을 import하지 않도록 구성했다.

## 4. Feature Flag 현황

| Flag | 기본값 | 역할 |
|---|---:|---|
| `RAG_LEXICAL_STRATEGY` | `legacy` | legacy 검색 / FTS5 선택 |
| `RAG_FUSION_STRATEGY` | `legacy_weighted` | 기존 fusion / RRF 선택 |
| `GROUNDING_VALIDATOR_ENABLED` | `false` | Validator 실행 |
| `GROUNDING_AUDIT_ENABLED` | `false` | 생성 후 Audit |
| `GROUNDING_DASHBOARD_ENABLED` | `false` | Dashboard 표시 |
| `GROUNDING_REPORT_EXPORT_ENABLED` | `false` | Grounding Report export |
| `WEB_GROUNDING_ENABLED` | `false` | Web Search 허용 |
| request `web_grounding` | `false` | 개별 생성의 Web Search 선택 |

Web Search는 환경 flag와 request option이 모두 활성화되고, 최근·현재·통계·뉴스·외부 연구 등 명시적 외부 사실 질의일 때만 최대 1회 호출된다.

## 5. Web Grounding 결과

- Provider: generic `HttpJsonWebSearchProvider` 1개
- endpoint: `WEB_SEARCH_ENDPOINT`
- 인증: `WEB_SEARCH_API_KEY` 환경변수 Bearer 방식
- timeout: 기본 10초, 5~15초 범위
- max results: 최대 5건
- 저장: DB가 아닌 runtime evidence
- 정규화: `EvidenceCandidate(source_type="web")`
- Grounding: 기존 Validator의 Tier D/weak 규칙 재사용
- URL: http/https만 허용, tracking parameter 제거, 중복 제거
- 실패: timeout·401/403·429·5xx·network error 모두 graceful fallback

실제 endpoint/API Key가 없는 환경이므로 Phase 3C live 평가는 skipped이며, deterministic mock 30 query 평가만 수행했다.

## 6. Phase 3C Mock 평가

| 지표 | 값 |
|---|---:|
| Query 수 | 30 |
| Success Rate | 90% (27/30) |
| Empty Result Rate | 10% (3/30) |
| Error Rate | 0% |
| Median latency | 0.02ms |
| P95 latency | 0.07ms |
| Metadata completeness | URL/title/published_at/provider 각 100% |
| Duplicate Rate | 0% |
| Grounding tier | D |

Mock 결과는 adapter·fallback·metadata 구조 검증용이며 실제 검색 품질을 의미하지 않는다.

## 7. 테스트 결과

- Phase 3B 관련 테스트 및 회귀: 32 passed
- Phase 3C 평가 테스트: 4 passed
- 최신 전체 pytest: **216 passed, failed=0, error=0**
- 컴파일 검사: 통과
- `app.main`, `app.core`, `app.providers.web` import 검사: 통과
- Web flag 기본값 확인: `False`

프로젝트 `.venv` 기준 baseline은 Phase 3B 직전 212 passed였으며, 현재 4개 평가 테스트 추가 후 216 passed다. 시스템 Python은 python-docx 누락으로 baseline에 사용하지 않았다.

## 8. 호환성·안전성

- 기존 API URL 유지
- 기존 request/response 형식 유지, Web option만 optional additive field
- SQLite schema migration 없음
- 기존 데이터 변경 없음
- Bible 중심본문 검증 우회 없음
- Tier A/B/C 정책 변경 없음
- FTS5/RRF 알고리즘 변경 없음
- LM Studio Provider 변경 없음
- 일반 Sermon Export에 Web Evidence 강제 삽입 없음
- Web Grounding OFF 시 Web Provider 호출 0회
- 순환 import 없음

## 9. 발견된 위험과 보류 사항

- Git metadata가 없어 branch/status를 확인할 수 없음
- 실제 Web Provider의 한국어 검색 품질·공식 출처 coverage·최신성·quota·비용은 미검증
- Provider별 JSON schema와 rate-limit semantics는 live contract test 필요
- Dashboard/Report의 Web Evidence 시각 표시 확장은 후속 승인 범위
- 실제 운영 활성화 전 API key와 endpoint에 대한 별도 보안·비용 승인 필요

## 10. Rollback

1. `WEB_GROUNDING_ENABLED=false` 유지 또는 복원
2. 요청의 `web_grounding` 생략 또는 false 처리
3. 필요 시 `app/providers/web`와 main/service 연결부 제거
4. 내부 Evidence/RAG/Grounding Pipeline 유지
5. 전체 pytest 재실행

Web Grounding은 DB에 저장하지 않으므로 DB rollback은 필요하지 않다.

## 11. 권장 다음 단계

1. 실제 Provider endpoint/API key를 별도 승인
2. 30개 Query × 1회 live 평가 실행
3. PASS면 Phase 3D-A(Query Builder/Web Evidence 품질 미세조정) 검토
4. 반복적인 품질·장애·rate-limit 문제가 확인될 때만 Phase 3D-B Multi-Provider + Failover 검토

이번 작업 이후 Multi-Provider, 자동 failover, 자동 웹 재검색, 자동 설교 재생성은 실행하지 않았다.

## 12. 관련 보고서

- [Phase 3B Web Grounding 보고서](PHASE3B_WEB_GROUNDING_REPORT.md)
- [Phase 3C Provider 평가 보고서](PHASE3C_WEB_PROVIDER_EVALUATION_REPORT.md)
- [평가 JSON](web_provider_evaluation.json)
