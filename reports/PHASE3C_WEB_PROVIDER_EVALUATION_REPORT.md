# Phase 3C Web Provider Evaluation Report

## 1. 작업 전 Baseline

- 제품: Sermon LM Studio V40.9.1
- 프로젝트 `.venv` baseline: 212 passed, failed=0, error=0
- Git status/branch: 현재 디렉터리에 `.git`이 없어 확인 불가
- `WEB_GROUNDING_ENABLED` 기본값: false

## 2. Provider 정보

현재 단일 Provider는 `HttpJsonWebSearchProvider`이며 endpoint는 `WEB_SEARCH_ENDPOINT`, 인증은 선택적 `WEB_SEARCH_API_KEY` 환경변수 Bearer 방식이다. timeout 기본 10초(5~15초 범위), max_results 최대 5, JSON 결과의 title/url/snippet/domain/published_at을 지원한다. 무료/유료 정책과 실제 rate limit은 endpoint 미설정으로 확인하지 못했다. API key 값은 기록하지 않았다.

## 3. 평가 환경

Windows 프로젝트 `.venv`, Python 3.x, 외부 endpoint/API key 미설정. CI/오프라인 재현성을 위해 deterministic MockProvider를 사용했다. 실제 네트워크 호출은 수행하지 않았다.

## 4. Query Set

`evaluation/web_queries.json`에 한국 공공 통계 5, 최근 사회 이슈 5, 국제 정보 5, 역사/배경 5, 영문 5, 실패/edge 5로 총 30개를 구성했다. 공식 기준은 한국 공공기관, UN/OECD/World Bank/WHO 등으로 정의했지만 mock 결과에는 적용하지 않았다.

## 5. 평가 방법

기존 `WebEvidenceAdapter`를 호출해 결과·latency·metadata를 수집하고 `reports/web_provider_evaluation.json`으로 저장했다. 실제 Provider 평가와 unit/mock 평가는 분리했다.

## 6. Success Rate

Mock: 90% (27/30). Edge fixture의 의도적 empty 결과 3건 때문이다. Live Provider success rate는 평가 skipped.

## 7. Error Rate

Mock: 0% (0/30). timeout/401/403/429/5xx는 별도 adapter unit test로 fallback을 확인했다. Live 수치는 미측정.

## 8. Empty Result Rate

Mock: 10% (3/30). 의도적 “존재하지 않는/모호한/결과가 거의 없는” 질의.

## 9. Latency

Mock 측정: average 0.02ms, median 0.02ms, p95 0.07ms, min 0.00ms, max 0.09ms. 네트워크 cold/warm 및 5/10/15초 timeout 분포는 live endpoint 부재로 미측정.

## 10. 한국어 검색 품질

Mock은 구조 검증용이므로 실제 한국어 relevance·기관 검색·encoding 품질은 판정하지 못했다.

## 11. 영문 검색 품질

Mock은 영문 의미 검색 품질을 판정하지 못했다. 한국어/영문 pair 비교는 live 평가에서 수행할 항목으로 남겼다.

## 12. 최신성 평가

Mock의 고정 published_at은 adapter 보존만 검증한다. 실제 최신 자료 노출 여부는 미측정이며 retrieved_at과 published_at 필드는 분리된다.

## 13. 공식 출처 Coverage

Mock 공식 출처 coverage: 0% (실제 기관 출처가 아님). Live Top-3 coverage는 endpoint 설정 후 재평가해야 한다.

## 14. Metadata Completeness

Mock 기준 URL/title/published_at/provider 100%. 실제 provider의 누락률은 미측정.

## 15. Duplicate Rate

Mock 결과 0%. Adapter는 normalized URL 기준 중복 제거를 수행한다.

## 16. Grounding 통합 확인

Adapter 결과는 `source_type=web`, 기존 Validator Tier D/weak로 전달된다. Validator 관련 unit test 통과.

## 17. Citation Traceability

EvidenceCandidate metadata에 title/domain/url/published_at/provider가 유지되어 Claim → Evidence → title → URL 추적이 가능하다. 자동 citation 삽입은 하지 않는다.

## 18. Offline 동작

기본 flag OFF 또는 endpoint 미설정 시 네트워크 요청 없이 빈 결과/fallback으로 내부 pipeline을 보존한다.

## 19. API Key 누락 처리

앱 시작 실패 없이 Provider가 빈 결과를 반환한다. key는 report·response·log에 저장하지 않는다.

## 20. 401/403 처리

HTTP 오류는 adapter 예외 경계에서 fallback으로 처리한다. 실제 응답은 mock하지 않고 기존 장애 테스트 방식으로 검증했다.

## 21. 429 처리

429 역시 generation으로 전파하지 않고 Web Grounding fallback으로 처리한다. 공격적인 부하 테스트는 하지 않았다.

## 22. Timeout 처리

Provider timeout은 10초 기본, 5~15초 범위로 제한되며 adapter가 빈 evidence로 복귀한다.

## 23. Provider 5xx 처리

5xx/네트워크 오류를 fallback 대상으로 처리한다.

## 24. 비용/Quota 분석

실제 endpoint와 요금 정보가 없어 비용·무료한도·quota는 추측하지 않았다.

## 25. 설교 1건당 예상 호출량

현재 구조는 명시적 `web_grounding=true` + 외부 사실 키워드 조건에서 최대 1 query, 결과 최대 5건이다. OFF는 0회.

## 26. 월간 예상 호출량

하루 1건: 월 약 30회, 하루 3건: 약 90회, 하루 10건: 약 300회(모두 조건 충족 시). 비용은 provider 요금 확인 후 계산한다.

## 27. 보안 점검

API key 환경변수 전용, URL scheme 검증, tracking parameter 정리, 전체 설교문/비공개 메모 미전송을 확인했다.

## 28. 전체 pytest 결과

새 평가 테스트 포함 `.venv\Scripts\python.exe -m pytest -q`: **216 passed**, failed=0, error=0.

## 29. 종합 평가

**PASS WITH WARNINGS** — adapter 안정성·오프라인 fallback·metadata/Tier 정책은 통과했으나 실제 Provider 품질과 latency는 endpoint 부재로 미검증이다.

## 30. 단일 Provider 유지 여부

유지한다. 현재 데이터만으로 다중 Provider 필요성을 입증할 수 없다.

## 31. Multi-Provider 필요 여부

이번 단계에서는 불필요/판정 보류. 실제 30 query live 평가에서 오류율·한국어 품질·공식 출처 coverage가 기준 미달일 때만 재검토한다.

## 32. 개선 권고

승인된 API key/endpoint가 준비되면 30 query × 1 run live 평가를 별도로 수행하고, query builder 문제와 provider 문제를 구분한다. Query Builder 대규모 수정이나 failover는 후속 단계로 미룬다.

## 33. 남은 위험

실제 provider별 JSON schema·rate limit·redirect·published_at 정확성·비용은 미검증이다. Mock 점수는 운영 품질을 대표하지 않는다.

## 34. Rollback / 변경사항 제거 방법

평가 도구 문제 시 `scripts/evaluate_web_provider.py`, `evaluation/web_queries.json`, `reports/web_provider_evaluation.json`, 본 보고서를 제거하고 기존 Phase 3B Web Grounding 코드는 유지한다. 서비스 flag는 계속 false로 둔다.

## 35. 다음 권장 단계

실제 Provider 자격증명과 endpoint를 별도 승인받은 뒤 live gate를 수동 실행한다. 결과가 PASS면 Phase 3D-A(Query Builder/Web Evidence 미세조정)를 검토하고, FAIL 또는 반복적 심각 경고일 때만 Phase 3D-B Multi-Provider + Failover를 제안한다. 이번 단계에서는 자동 후속 구현을 하지 않는다.
