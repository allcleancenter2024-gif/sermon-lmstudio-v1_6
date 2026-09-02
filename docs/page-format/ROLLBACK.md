# Rollback

## 설정 rollback

```text
PAGE_FORMAT_V2=false
PAGE_FORMAT_ROLLOUT=legacy
```

legacy exporter와 fallback은 rollback window 동안 삭제하지 않는다.

## 확인 순서

1. 서버 재시작 및 `/api/runtime` 확인
2. 인증된 HTML·PDF·DOCX 출력
3. source/citation 확인
4. fallback·telemetry 확인
5. 전체 회귀 테스트

## 기준점

- 버전: `40.9.10`
- known-good regression: `287 passed, 7 subtests passed`
- V2 100% 선택 검증: PASS

Git history와 기존 `ROLLBACK_V40*.md` 문서를 함께 사용한다. DB·백업·export 파일은 rollback 과정에서 삭제하지 않는다.
