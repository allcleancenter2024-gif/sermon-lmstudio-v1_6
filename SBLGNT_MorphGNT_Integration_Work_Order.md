# SBLGNT · MorphGNT 안전 도입 작업지시서
## Codex CLI용 — 신약 헬라어 원문/형태론/본문비평 데이터 통합

- 문서 목적: SBLGNT 신약 헬라어 원문, MorphGNT 형태론, SBLGNT Apparatus를 기존 애플리케이션에 **구조 충돌 없이 단계적으로 도입**
- 권장 방식: **Staging → 검증 → 파서 → 정규화 DB → 서비스 레이어 → 선택적 RAG**
- 우선 원칙: **원문(Source of Truth)과 AI 해석을 절대 혼합하지 않는다**
- 기준일: 2026-09-02
- 실행 대상: Codex CLI / 로컬 개발 환경
- 기본 모드: 기존 기능 보존, 비파괴적 작업, 단계별 테스트 우선

---

# 1. 작업 목표

현재 애플리케이션에 신약 헬라어 데이터를 추가한다.

구축 대상은 다음 3개 계층으로 분리한다.

1. **SBLGNT**
   - 신약 헬라어 원문
   - 책별 XML
   - 전체 통합 XML

2. **MorphGNT**
   - lemma
   - 품사
   - 형태론 parsing
   - normalized form

3. **SBLGNT Apparatus**
   - 본문비평 자료
   - WH / Treg / NA 계열 / RP 등의 이문 비교 정보
   - 성경 원문과는 별도 저장

최종적으로 다음 질의를 안정적으로 처리할 수 있어야 한다.

예:

```text
요한복음 8:32 헬라어 원문을 보여줘.
요한복음 8:32의 핵심 단어를 형태론적으로 분석해줘.
ἀλήθεια의 lemma와 형태를 알려줘.
고린도전서 13:4의 헬라어 본문과 형태론을 보여줘.
```

---

# 2. 공식 데이터 소스

## 2.1 SBLGNT

공식 프로젝트:

```text
https://github.com/Faithlife/SBLGNT
```

SBLGNT 공식 다운로드 페이지:

```text
https://www.sblgnt.com/download/
```

XML 원문 디렉터리:

```text
data/sblgnt/xml/
```

대표 파일:

```text
Matt.xml
Mark.xml
Luke.xml
John.xml
Acts.xml
Rom.xml
1Cor.xml
...
Rev.xml
sblgnt.xml
```

`data/sblgnt/xml/`의 자료를 **신약 헬라어 원문 Source of Truth**로 사용한다.

---

## 2.2 SBLGNT 라이선스

공식 라이선스:

```text
Creative Commons Attribution 4.0 International
CC BY 4.0
```

공식 라이선스 페이지:

```text
https://www.sblgnt.com/license/
```

프로젝트 내부에 반드시 attribution 정보를 보존한다.

권장 예:

```text
The Greek New Testament: SBL Edition (SBLGNT)
Editor: Michael W. Holmes
Copyright © 2010 Society of Biblical Literature and Logos Bible Software
License: Creative Commons Attribution 4.0 International
Source: https://github.com/Faithlife/SBLGNT
```

원본을 수정하거나 변환한 데이터를 배포할 경우 변경 사실도 기록한다.

---

# 3. MorphGNT

공식 프로젝트:

```text
https://github.com/morphgnt/sblgnt
```

MorphGNT는 SBLGNT 본문에 형태론과 lemma 정보를 결합한 데이터이다.

대표 컬럼:

```text
book/chapter/verse
part of speech
parsing code
text
word
normalized word
lemma
```

대표 파일:

```text
61-Mt-morphgnt.txt
62-Mk-morphgnt.txt
63-Lk-morphgnt.txt
64-Jn-morphgnt.txt
...
67-1Co-morphgnt.txt
...
87-Re-morphgnt.txt
```

주의:

MorphGNT README는 기존 POS/parsing 코드 체계가 향후 major release에서 deprecated될 수 있다고 설명한다.

따라서 애플리케이션 내부 로직을 MorphGNT raw code에 강하게 결합하지 않는다.

반드시:

```text
raw 값
+
normalized 값
```

을 모두 보존한다.

예:

```text
pos_raw
parse_raw

pos_normalized
person
tense
voice
mood
case
number
gender
degree
```

---

# 4. 가장 중요한 설계 원칙

다음 데이터를 하나의 테이블 또는 하나의 JSON에 무조건 합치지 않는다.

```text
SBLGNT 원문
MorphGNT 형태론
SBLGNT Apparatus
번역본
주석
설교 자료
AI 생성 해석
```

권장 계층:

```text
Layer 1
SBLGNT
신약 헬라어 원문

        ↓

Layer 2
MorphGNT
lemma / morphology

        ↓

Layer 3
Textual Apparatus
본문비평

        ↓

Layer 4
Lexicon
원어 사전

        ↓

Layer 5
Translations
번역본

        ↓

Layer 6
Commentary / Theology
주석 · 신학 자료

        ↓

Layer 7
RAG

        ↓

Layer 8
LLM
설명 · 요약 · 설교 생성
```

---

# 5. 권장 디렉터리 구조

기존 프로젝트 구조를 먼저 조사한 후 가장 가까운 데이터 디렉터리에 적용한다.

새 루트가 필요한 경우 다음 구조를 권장한다.

```text
data/
└── biblical_sources/
    └── greek_nt/
        │
        ├── sblgnt/
        │   ├── raw/
        │   │   ├── books/
        │   │   │   ├── Matt.xml
        │   │   │   ├── Mark.xml
        │   │   │   ├── Luke.xml
        │   │   │   ├── John.xml
        │   │   │   ├── ...
        │   │   │   ├── 1Cor.xml
        │   │   │   └── Rev.xml
        │   │   │
        │   │   └── full/
        │   │       └── sblgnt.xml
        │   │
        │   ├── metadata/
        │   │   ├── source.json
        │   │   ├── VERSION
        │   │   ├── ATTRIBUTION.md
        │   │   └── LICENSE
        │   │
        │   └── staging/
        │
        ├── morphgnt/
        │   ├── raw/
        │   ├── normalized/
        │   ├── metadata/
        │   └── staging/
        │
        ├── apparatus/
        │   └── sblgntapp/
        │       ├── raw/
        │       ├── normalized/
        │       └── metadata/
        │
        └── indexes/
```

기존 프로젝트에 이미 `sources`, `datasets`, `corpus` 등의 구조가 있다면 중복 폴더를 만들지 말고 기존 규칙을 따른다.

---

# 6. 작업 절차

## Phase 0 — 구조 조사

**아직 소스 코드를 수정하지 않는다.**

먼저 다음을 조사한다.

```text
1. 프로젝트 루트
2. 현재 데이터 디렉터리
3. Bible 관련 모듈 존재 여부
4. Repository 계층 존재 여부
5. PostgreSQL 연결 구조
6. pgvector 사용 여부
7. migration 도구
8. 테스트 구조
9. 기존 성경 Reference Parser 존재 여부
10. 기존 RAG ingestion pipeline
```

다음 파일이 있다면 우선 확인한다.

```text
AGENTS.md
README.md
docker-compose.yml
docker-compose.yaml
.env.example
requirements.txt
pyproject.toml
package.json
alembic.ini
```

결과를 먼저 보고한다.

---

# 7. Phase 1 — 데이터 Staging

공식 소스 데이터를 곧바로 production DB에 넣지 않는다.

먼저 staging 영역에 저장한다.

```text
data/biblical_sources/greek_nt/.../staging/
```

검증 항목:

```text
[ ] 다운로드 성공
[ ] XML parse 성공
[ ] UTF-8 처리 성공
[ ] Greek Unicode 정상
[ ] 파일명 정상
[ ] 27권 존재
[ ] 중복 파일 없음
[ ] 비어 있는 파일 없음
[ ] source metadata 존재
[ ] license/attribution 존재
```

---

# 8. Phase 2 — SBLGNT XML Parser

전용 parser를 작성한다.

예시 모듈:

```text
app/
└── biblical/
    └── greek/
        ├── parser/
        │   └── sblgnt_parser.py
        ├── models/
        ├── repositories/
        └── services/
```

단, 실제 프로젝트 architecture를 먼저 확인하고 현재 규칙에 맞춘다.

Parser의 책임:

```text
XML
 ↓
Book
 ↓
Chapter
 ↓
Verse
 ↓
Token / Text
```

최소 표준 출력:

```json
{
  "source": "SBLGNT",
  "book": "John",
  "book_code": "JHN",
  "chapter": 8,
  "verse": 32,
  "reference": "JHN.8.32",
  "greek_text": "...",
  "source_version": "..."
}
```

---

# 9. Reference 표준화

프로젝트 전체에서 성경 구절 ID를 하나로 통일한다.

권장 내부 canonical reference:

```text
JHN.8.32
MAT.5.3
1CO.13.4
ROM.8.1
```

별칭 입력은 별도 mapper에서 처리한다.

예:

```text
John 8:32
Jn 8:32
JHN 8:32
요 8:32
요한복음 8:32
```

모두:

```text
JHN.8.32
```

로 정규화한다.

원문 데이터에는 표시용 이름과 canonical code를 둘 다 저장한다.

---

# 10. PostgreSQL 권장 데이터 모델

## 10.1 bible_sources

```text
id
source_key
title
version
language
license
attribution
source_url
retrieved_at
checksum
metadata_json
```

---

## 10.2 bible_verses

```text
id
source_id
book_code
chapter
verse
canonical_reference
text
normalized_text
metadata_json
```

Unique constraint:

```text
source_id
book_code
chapter
verse
```

---

## 10.3 greek_tokens

```text
id
verse_id
position

surface
normalized
lemma

pos_raw
parse_raw

pos_normalized

person
tense
voice
mood
case
number
gender
degree

source
source_version
metadata_json
```

중요:

```text
surface
lemma
pos_raw
parse_raw
```

값을 절대 버리지 않는다.

---

## 10.4 textual_variants

본문비평 자료는 별도 테이블로 둔다.

```text
id
verse_id
token_position
apparatus_source
reading
witness
category
note
metadata_json
```

---

# 11. pgvector 사용 원칙

성경 원문 lookup 자체에 pgvector를 우선 사용하지 않는다.

## 정확한 구절 조회

다음은 SQL exact lookup을 사용한다.

```text
요한복음 8:32
마태복음 5:3
고린도전서 13:4
```

흐름:

```text
Reference Parser
      ↓
Canonical Reference
      ↓
PostgreSQL Exact Lookup
      ↓
SBLGNT
```

---

## Semantic Search

pgvector는 다음에 사용한다.

```text
주석
신학 문서
교리 문서
설교 자료
관련 구절 탐색
주제 검색
교육 자료
```

즉:

```text
Bible Text = Exact DB
Commentary/RAG = Vector DB
```

원칙을 유지한다.

---

# 12. MorphGNT 결합 방식

SBLGNT 원문을 기준으로 MorphGNT token을 연결한다.

절대 MorphGNT 데이터만으로 원문 DB를 대체하지 않는다.

권장:

```text
SBLGNT verse
       ↓
SBLGNT tokens
       ↓
MorphGNT alignment
       ↓
lemma / morphology
```

매칭 검증:

```text
reference
token order
surface form
normalized form
```

불일치 시 자동 수정하지 않는다.

다음 상태로 기록한다.

```text
MATCHED
NORMALIZATION_ONLY
TOKENIZATION_DIFFERENCE
TEXT_DIFFERENCE
UNRESOLVED
```

---

# 13. John 7:53–8:11 주의

SBLGNT 데이터의 버전 차이가 발생할 수 있으므로 이 구간은 특별 검증한다.

반드시 확인:

```text
John 7:53
John 8:1
...
John 8:11
```

MorphGNT release와 SBLGNT release 사이에 이 구간 포함 여부가 다를 가능성이 있으므로 자동 alignment 실패를 오류로 종료하지 말고 별도 report로 남긴다.

---

# 14. XML 보안

XML parser는 외부 entity를 기본 비활성화한다.

금지:

```text
DTD external entity resolution
remote XML entity loading
network access during parsing
```

가능하다면 hardened XML parser 또는 안전 설정을 사용한다.

---

# 15. Unicode 정책

헬라어 원문은 Unicode를 임의로 ASCII 변환하지 않는다.

보존:

```text
polytonic Greek
breathing marks
accents
iota subscript
punctuation
```

검색용 normalized field는 별도로 생성한다.

즉:

```text
surface
normalized
```

를 분리한다.

원본 surface 값은 절대 덮어쓰지 않는다.

---

# 16. 원문 신뢰도 보호

LLM이 다음 값을 생성해서 원문 DB에 저장하는 것을 금지한다.

```text
Greek Bible text
lemma
morphology
textual variant
Bible reference
```

DB 저장 데이터는 공식 corpus에서 파싱한 결과만 허용한다.

AI 결과는 반드시 별도 영역에 둔다.

예:

```text
ai_explanations
sermon_drafts
study_notes
```

---

# 17. 테스트 요구사항

## Unit Test

```text
SBLGNT XML parser
reference parser
book mapper
MorphGNT parser
token alignment
Unicode normalization
license metadata loader
```

---

## Integration Test

최소 다음 구절을 사용한다.

```text
MAT.1.1
JHN.1.1
JHN.3.16
JHN.8.32
ROM.8.1
1CO.13.4
REV.22.21
```

검증:

```text
reference lookup
Greek text retrieval
token count
lemma retrieval
morphology retrieval
source metadata
```

---

# 18. 전체 Corpus 검증

다음 검사를 자동화한다.

```text
27 books found
all XML parseable
no empty books
chapter numbers valid
verse numbers valid
canonical references unique
no duplicate verses
Greek text not empty
source id present
source version present
```

MorphGNT:

```text
27 files found
all rows parseable
all references valid
lemma not unexpectedly empty
raw parse code retained
alignment report generated
```

---

# 19. Checksum

외부 원본 파일은 checksum을 기록한다.

권장:

```text
SHA-256
```

예:

```json
{
  "source": "Faithlife/SBLGNT",
  "file": "John.xml",
  "sha256": "...",
  "retrieved_at": "...",
  "source_url": "...",
  "version": "..."
}
```

이를 통해 나중에 corpus 변경 여부를 감지할 수 있게 한다.

---

# 20. 업데이트 정책

외부 Git repository의 `master/main`을 production에서 매번 직접 참조하지 않는다.

권장:

```text
approved source revision
        ↓
checksum
        ↓
staging
        ↓
validation
        ↓
promote
```

가능하면 commit SHA 또는 release/tag를 기록한다.

업데이트 시:

```text
OLD VERSION
NEW VERSION
DIFF
VALIDATION
MIGRATION
```

순서로 수행한다.

---

# 21. Repository / Service 분리

애플리케이션 코드가 XML 파일을 직접 여기저기 읽지 않게 한다.

권장 계층:

```text
Controller / API
       ↓
GreekTextService
       ↓
BibleRepository
       ↓
PostgreSQL
```

원본 XML:

```text
Ingestion Pipeline
       ↓
Parser
       ↓
Validation
       ↓
Repository
       ↓
PostgreSQL
```

---

# 22. API 예시

기존 API 설계를 해치지 않는 범위에서 다음 형태를 검토한다.

```text
GET /api/bible/greek/JHN/8/32
```

응답 예:

```json
{
  "reference": "JHN.8.32",
  "source": "SBLGNT",
  "text": "...",
  "tokens": [],
  "attribution": {}
}
```

형태론:

```text
GET /api/bible/greek/JHN/8/32/morphology
```

본문비평:

```text
GET /api/bible/greek/JHN/8/32/apparatus
```

하나의 endpoint에 모든 정보를 억지로 넣지 않는다.

---

# 23. UI 적용 원칙

기존 UI를 대규모로 변경하지 않는다.

필요 시 다음 정도만 추가한다.

```text
헬라어 원문
원어 분석
본문비평
출처
```

표시 예:

```text
요한복음 8:32

[SBLGNT]
Greek text

[형태론]
word | lemma | POS | parsing

[출처]
SBLGNT
MorphGNT
```

AI 설명과 원문 데이터는 시각적으로 구분한다.

---

# 24. Attribution UI

사용자에게 데이터 출처를 확인할 수 있도록 한다.

예:

```text
Source: SBL Greek New Testament
Editor: Michael W. Holmes
License: CC BY 4.0
```

MorphGNT 형태론은 MorphGNT attribution을 별도 표기한다.

---

# 25. 하지 말아야 할 것

다음을 금지한다.

```text
[금지] production DB에 바로 import
[금지] 기존 Bible 데이터 삭제
[금지] 기존 migrations 수정
[금지] 원문과 AI 생성문 혼합
[금지] MorphGNT를 원문 source of truth로 대체
[금지] XML raw files를 임의 편집
[금지] license/attribution 제거
[금지] parsing code를 애플리케이션 전역 enum에 강결합
[금지] pgvector만으로 Bible reference lookup 구현
[금지] alignment 오류 자동 은폐
```

---

# 26. 구현 순서

반드시 아래 순서대로 진행한다.

```text
Phase 0
Repository 구조 분석

Phase 1
공식 자료 다운로드 / revision 고정

Phase 2
Staging

Phase 3
Checksum + License metadata

Phase 4
SBLGNT Parser

Phase 5
Corpus Validator

Phase 6
MorphGNT Parser

Phase 7
Token Alignment

Phase 8
DB Schema / Migration

Phase 9
Repository

Phase 10
Service Layer

Phase 11
API

Phase 12
UI

Phase 13
RAG 연결

Phase 14
Regression Test
```

---

# 27. 각 Phase 완료 조건

각 Phase가 끝날 때 다음 형식으로 보고한다.

```text
## Phase N 결과

### 변경 파일
- ...

### 신규 파일
- ...

### 테스트
- PASS:
- FAIL:

### 기존 기능 영향
- 없음 / 있음

### 발견 문제
- ...

### 다음 단계
- ...
```

실패를 숨기거나 우회하지 않는다.

---

# 28. Rollback 전략

각 DB migration에는 downgrade/rollback 방법을 제공한다.

데이터 import는 재실행 가능해야 한다.

즉:

```text
idempotent ingestion
```

을 목표로 한다.

동일 corpus를 두 번 import해도 중복 verse가 생성되지 않아야 한다.

---

# 29. 성능 원칙

성경 구절 exact lookup은 빠른 SQL index를 사용한다.

권장 index:

```text
(book_code, chapter, verse)
canonical_reference
lemma
normalized
```

27권 XML을 매 요청마다 다시 parse하지 않는다.

XML은 ingestion 시 한 번 처리하고 runtime에서는 DB를 사용한다.

---

# 30. 로그

다음 이벤트를 기록한다.

```text
corpus ingestion started
corpus ingestion completed
file checksum mismatch
xml parse error
duplicate reference
morph alignment mismatch
migration error
```

단, 일반 요청마다 전체 Greek text를 로그에 반복 저장하지 않는다.

---

# 31. 최종 테스트 시나리오

### Test A

입력:

```text
요한복음 8:32
```

기대:

```text
JHN.8.32
→ SBLGNT exact lookup
→ Greek text
```

---

### Test B

입력:

```text
요한복음 8:32 원어 분석
```

기대:

```text
SBLGNT
+
MorphGNT
```

---

### Test C

입력:

```text
ἀλήθεια
```

기대:

```text
lemma search
+
occurrence search
```

---

### Test D

입력:

```text
고린도전서 13:4 헬라어
```

기대:

```text
1CO.13.4
```

---

### Test E

RAG 장애 발생

기대:

```text
성경 원문 조회는 정상 동작
```

즉 원문 시스템은 RAG 시스템 장애와 분리되어야 한다.

---

# 32. Codex에게 주는 최종 지시

아래 조건을 반드시 준수한다.

```text
1. 먼저 프로젝트 구조를 분석한다.
2. 분석 전에는 파일을 수정하지 않는다.
3. 기존 architecture를 최대한 유지한다.
4. SBLGNT를 Greek NT Source of Truth로 사용한다.
5. MorphGNT는 morphology layer로 분리한다.
6. Apparatus는 별도 데이터 계층으로 분리한다.
7. DB import 전 staging validation을 수행한다.
8. 라이선스와 attribution을 보존한다.
9. reference lookup은 PostgreSQL exact lookup을 기본으로 한다.
10. pgvector는 semantic 자료 검색에만 우선 사용한다.
11. original raw data를 수정하지 않는다.
12. 모든 변환 데이터에는 source/version/checksum을 기록한다.
13. 기존 기능 regression test를 수행한다.
14. 문제가 발견되면 임의 수정하지 말고 원인과 영향 범위를 먼저 보고한다.
15. 작업 완료 후 변경 파일·테스트·위험·rollback 방법을 보고한다.
```

---

# 33. Codex 실행용 프롬프트

다음 내용을 Codex CLI에 전달한다.

```text
현재 프로젝트를 분석하고 신약 헬라어 데이터 계층 도입을 준비하라.

목표:
Faithlife/SBLGNT의 XML 원문을 Source of Truth로 사용하고,
MorphGNT를 별도의 lemma/morphology layer로 연결하며,
SBLGNT apparatus는 별도의 textual criticism layer로 분리한다.

중요:
지금 즉시 대규모 구현부터 시작하지 말라.

먼저 다음을 수행하라.

1. 현재 repository 구조 분석
2. Bible/RAG/Repository/DB 관련 코드 탐색
3. PostgreSQL 및 pgvector 구조 확인
4. migration 방식 확인
5. 기존 reference parser 확인
6. 기존 데이터 ingestion pipeline 확인
7. SBLGNT 도입 시 충돌 가능성 분석
8. 필요한 신규/수정 파일 목록 제안
9. DB schema 초안 제시
10. 테스트 계획 제시

설계 원칙:
- SBLGNT = Greek NT Source of Truth
- MorphGNT = morphology/lemma layer
- Apparatus = separate textual criticism layer
- Bible exact lookup = PostgreSQL
- Semantic search = pgvector
- Raw corpus immutable
- source/version/checksum 저장
- license/attribution 보존
- AI generated text와 corpus 분리
- staging validation 후 production promotion
- idempotent ingestion
- rollback 가능 구조

특히 John 7:53–8:11의 source-version 차이를 별도로 검증하라.

분석 단계에서는 기존 파일을 수정하지 말라.

먼저 다음 형식으로 보고하라.

A. 현재 구조
B. 재사용 가능한 기존 모듈
C. 예상 충돌
D. 권장 구조
E. DB 설계
F. Migration 계획
G. 테스트 계획
H. 변경 예정 파일
I. 위험 요소
J. Rollback 전략

분석 결과가 안전할 때에만 다음 구현 단계를 제안하라.
```

---

# 34. 권장 최종 구조

```text
               ┌─────────────────────┐
               │ User Bible Request  │
               └──────────┬──────────┘
                          │
                  Reference Parser
                          │
                     JHN.8.32
                          │
             ┌────────────▼────────────┐
             │ PostgreSQL Bible Core  │
             └────────────┬────────────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
          SBLGNT       MorphGNT    Apparatus
           Text        Morphology    Variants
              │           │           │
              └───────────┼───────────┘
                          │
                     Greek Service
                          │
             ┌────────────▼────────────┐
             │ Commentary / Theology  │
             │        pgvector        │
             └────────────┬────────────┘
                          │
                         LLM
                          │
                 Explanation/Sermon
```

가장 중요한 원칙:

```text
성경 원문은 AI가 생성하지 않는다.
AI는 검증된 성경 데이터를 읽고 설명한다.
```

---

# 35. 참고 출처

## SBLGNT 공식 다운로드

https://www.sblgnt.com/download/

## SBLGNT 공식 라이선스

https://www.sblgnt.com/license/

## Faithlife SBLGNT GitHub

https://github.com/Faithlife/SBLGNT

## Faithlife SBLGNT XML

https://github.com/Faithlife/SBLGNT/tree/master/data/sblgnt/xml

## MorphGNT SBLGNT

https://github.com/morphgnt/sblgnt

---

# 36. 권장 판단

**도입 권장: YES**

단, 다음 방식만 권장한다.

```text
공식 원본
→ revision 고정
→ staging
→ checksum
→ corpus validation
→ parser
→ normalized DB
→ repository/service
→ API
→ RAG
→ LLM
```

반대로 다음 방식은 권장하지 않는다.

```text
GitHub 파일 다운로드
→ 바로 production DB import
→ LLM/RAG와 한 테이블에 혼합
```

이 문서를 마스터 작업지시서로 사용하고, 실제 구현은 Phase별로 분리해서 수행한다.
