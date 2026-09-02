# Page Format Skill Phase PF-6 진행·검증 보고서

## Overall Status

`PASS_WITH_WARNINGS`

이번 단계에서 V2 기본값 전환과 주요 release gate 검증은 완료했다. 다만 legacy 경로는 rollback·fallback·기존 export 호환성을 위해 유지했고, 별도 visual baseline 비교와 장기 운영 관찰은 후속 작업으로 남겼다.

## Final State

- `CLEANUP_COMPLETE`: PARTIAL
- `SKILL_RELEASE_READY`: NO
- `LEGACY_PRESENT`: YES
- `V2_DEFAULT_ACTIVE`: YES
- `MAINTENANCE_MODE`: 준비 단계

## Preconditions

- PF-5 Status: `PASS_WITH_WARNINGS`
- V2 100% canary: 통과
- 인증된 HTML/PDF/DOCX 출력: 통과
- rollback 경계: 통과

## 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `app/formatting/format_router.py` | `PAGE_FORMAT_V2` 기본값을 `true`로 전환 |
| `tests/test_page_format.py` | V2 기본값 활성화에 맞게 기대값 조정 |
| `.agents/skills/page-format/SKILL.md` | V2 기본값 및 legacy rollback 설명 정합화 |
| `.agents/skills/page-format/references/default-rollout.md` | rollout 완료 후 기본값·rollback 절차 정합화 |
| `PAGE_FORMAT_SKILL_INTEGRATION_PHASE6_PROGRESS_REPORT.md` | 본 작업 결과 기록 |

canonical 문서는 `docs/page-format/`에 추가했다. README, ARCHITECTURE, PROFILES, EXPORTS, QUALITY, ROLLBACK, MAINTENANCE의 7개 문서와 내부 링크를 검증했다.

## Canary History

| 단계 | 선택률 검증 | 인증 출력 | 관련 테스트 | 판정 |
|---:|---:|---|---:|---|
| 1% | 1.08% | HTML/PDF/DOCX PASS | 21 passed | PASS |
| 5% | 4.67% | HTML/PDF/DOCX PASS | 21 passed | PASS |
| 10% | 9.67% | HTML/PDF/DOCX PASS | 21 passed | PASS |
| 25% | 24.78% | HTML/PDF/DOCX PASS | 21 passed | PASS |
| 50% | 49.83% | HTML/PDF/DOCX PASS | 21 passed | PASS |
| 100% | 100.00% | HTML/PDF/DOCX PASS | 21 passed | PASS |

모든 canary는 `127.0.0.1`의 별도 포트에서 실행했고, 검증 후 프로세스와 포트를 정리했다. 운영 기본값은 최종 기본값 전환 시점까지 별도로 보호했다.

## Tests and Quality Gates

- Page Format 관련 테스트: `21 passed`
- 전체 회귀 테스트: `287 passed, 7 subtests passed`
- Document golden: 7개 `VALID`
- HTML golden: `VALID`
- PDF smoke: 확인 파일 5개 모두 `VALID`
- DOCX smoke: 확인 파일 5개 모두 `VALID DOCX`
- canonical 문서 링크: 누락 0건
- fallback 이벤트: `0`
- 최근 HTML 품질 점수: `100`
- telemetry 평균 품질 점수: `98.86`
- telemetry에 원문·성경 본문·RAG evidence·API key·개인 식별자 기록 없음

## Legacy and Feature Flags

| 항목 | 상태 | 조치 |
|---|---|---|
| `PAGE_FORMAT_V2` | ACTIVE | 기본값 `true`; `false`는 명시적 rollback switch |
| `PAGE_FORMAT_ROLLOUT` | ACTIVE | `legacy`, percentage, `100` 경로 유지 |
| `ALLOW_LEGACY_FALLBACK` | ACTIVE | 오류 시 안전한 fallback 유지 |
| legacy exporters | KEEP_FOR_ROLLBACK | 기존 PDF/DOCX 및 호환 테스트가 사용하므로 삭제하지 않음 |
| 불명확한 dead code | UNKNOWN | 삭제하지 않음 |

## UI and Workflow Verification

- 좌측 주메뉴 복구 확인
- 메뉴 접기/다시 펼치기 기능 확인
- `설교문 제작 흐름` 배경 박스 제거
- 단계 번호 원형 표시
- 단계 라벨 굵게 표시
- 현재 단계 진한 파란색 표시
- 현재 선택 테두리 `0.8mm` 적용
- 모바일·1024px·1440px 가로 overflow 점검 통과

## Rollback

긴급 rollback 시 legacy 경로를 명시한다.

```text
PAGE_FORMAT_V2=false
PAGE_FORMAT_ROLLOUT=legacy
```

rollback 후 확인할 항목:

1. HTML·PDF·DOCX 출력
2. protected API 인증 응답
3. fallback 및 telemetry
4. 전체 회귀 테스트

## 남은 위험과 후속 작업

- legacy runtime call site가 남아 있으므로 현재 삭제하지 않음
- visual regression baseline을 동일 OS·브라우저·폰트 조건으로 별도 고정할 필요가 있음
- 성능 baseline을 p50/p95 및 환경 metadata와 함께 별도 문서화할 필요가 있음
- canonical `docs/page-format/` 문서 구조 통합: 완료
- maintenance runbook: `docs/page-format/MAINTENANCE.md` 작성 완료
- rollback 문서: `docs/page-format/ROLLBACK.md` 작성 완료
- 별도 release manifest/changelog: 기존 version convention과 중복될 수 있어 추가하지 않음
- 테스트 디렉터리 일부는 Windows ACL 제한으로 일반 inventory 순회가 불안정함

## 최종 권고

현재 코드와 출력 기능은 V2 기본값으로 운용 가능한 상태이며, legacy fallback을 유지하는 조건에서 안정적으로 보존된다. canonical 문서와 maintenance/rollback 기록은 정리했지만, 동일 환경의 visual baseline 및 장기 성능 baseline이 고정되지 않아 `SKILL_RELEASE_READY`는 `NO`로 유지한다.

다음 변경은 새 기능 추가가 아니라 visual baseline, 성능 baseline, canonical 문서 및 maintenance runbook을 별도 작은 batch로 정리하는 방식이 안전하다.
