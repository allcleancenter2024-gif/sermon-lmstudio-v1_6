# Page Format

구조화된 설교·성경 분석·RAG 근거 자료를 Markdown, HTML, Dashboard, PDF, DOCX로 표현하는 로컬 출력 계층이다.

## 기본 원칙

- 검증된 `Document`만 렌더링한다.
- V2 renderer를 기본값으로 사용한다.
- `PAGE_FORMAT_V2=false`와 `PAGE_FORMAT_ROLLOUT=legacy`를 rollback 경로로 유지한다.
- 성경 본문·근거·출처 metadata를 출력 형식 사이에서 보존한다.
- 원문·개인정보·API key는 telemetry에 기록하지 않는다.

## 문서

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [PROFILES.md](PROFILES.md)
- [EXPORTS.md](EXPORTS.md)
- [QUALITY.md](QUALITY.md)
- [ROLLBACK.md](ROLLBACK.md)
- [MAINTENANCE.md](MAINTENANCE.md)

세부 검증 규칙은 [Page Format Skill](../../.agents/skills/page-format/SKILL.md)과 그 `references/`를 따른다.
