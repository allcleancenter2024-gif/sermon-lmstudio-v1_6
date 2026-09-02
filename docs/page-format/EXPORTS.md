# Exports

| Format | 용도 | 검증 기준 | 제한 |
|---|---|---|---|
| Markdown | canonical source export | source metadata, Unicode | 인쇄 레이아웃 없음 |
| HTML | 웹·브라우저 출력 | escaping, security, accessibility | 외부 tracker·CDN 금지 |
| Dashboard | 운영 상태 시각화 | semantic structure, contrast | 문서 본문 생성용 아님 |
| PDF | 인쇄·배포 | open, pages, headings, sources, Unicode | ReportLab/Windows 환경 의존 |
| DOCX | 편집 가능한 문서 | open, styles, headings, sources, Unicode | 기존 exporter adapter 유지 |

모든 형식은 source identity와 citation metadata를 보존해야 한다. 출력 오류는 quality gate를 통과시키기 위해 숨기지 않는다.
