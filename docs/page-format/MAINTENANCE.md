# Maintenance Runbook

## 변경 절차

1. Document contract와 registry 호환성 확인
2. 변경 전 관련 테스트 실행
3. 필요한 경우 fixture와 golden sample 추가
4. security·accessibility·Unicode·source gate 실행
5. PDF/DOCX smoke 실행
6. 전체 회귀 실행
7. rollback 방법과 변경 파일 기록

## Profile·theme·preset

- profile: contract, fixture, golden, source integrity, accessibility 필수
- theme: token, contrast, focus, non-color status, mobile·print 확인
- preset: compatibility matrix, validator, fixture, export smoke 확인

## Baseline 변경

baseline을 테스트 통과 목적으로 자동 갱신하지 않는다. 변경 시 이전 값, 새 값, 이유, 영향, 승인 맥락을 기록한다.

## 운영 점검

telemetry에는 render count, format, status, fallback, quality, latency만 기록한다. 설교문·성경 본문·RAG evidence·업로드 파일·API key·개인 식별자는 기록하지 않는다.
