# Quality and Release Gates

## 필수 gate

- Document model validation
- HTML security 및 escaping
- Accessibility: keyboard, focus, heading, contrast, reflow, accessible name
- Greek/Hebrew Unicode 및 combining mark 보존
- Source/citation integrity
- PDF/DOCX open·structure·Unicode 검사
- golden sample 비교
- 관련 테스트와 전체 회귀 테스트

critical failure는 quality score로 상쇄하지 않는다.

## 현재 baseline

- Page Format 관련 테스트: `21 passed`
- 전체 회귀: `287 passed, 7 subtests passed`
- Document golden: 7개 `VALID`
- HTML golden: `VALID`
- PDF smoke: 확인 파일 5개 `VALID`
- DOCX smoke: 확인 파일 5개 `VALID DOCX`
- fallback: `0`
- telemetry 평균 quality score: `98.86`
- 최근 HTML quality score: `100`

Visual regression과 장기 성능 관찰은 별도 환경 baseline을 고정할 때까지 release warning으로 관리한다.
