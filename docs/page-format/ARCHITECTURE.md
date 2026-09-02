# Architecture

```text
Content Generator
      ↓
Structured Document Model
      ↓
Adapters
      ↓
Page Format Router
      ↓
Profile / Template / Theme / Preset
      ↓
Renderer
      ↓
Quality Gates
      ↓
Markdown / HTML / Dashboard / PDF / DOCX
```

주요 구현 경계:

- `app/formatting/document_model.py`: Document, Section, ContentBlock, Source와 입력 검증
- `app/formatting/adapters/`: 기존 응답을 Document로 변환
- `app/formatting/registry.py`: profile·theme·template·preset 호환성
- `app/formatting/format_router.py`: V2 선택과 형식별 렌더링
- `app/formatting/fallback.py`: 허용된 비검증 오류의 legacy fallback
- `app/formatting/telemetry.py`: 기술 metadata만 기록
- `app/routers/exports.py`: 기존 API와 export 응답 호환성 유지

PDF와 DOCX는 기존 exporter adapter를 재사용한다. 이 경계는 legacy 호환성과 rollback을 위해 유지한다.
