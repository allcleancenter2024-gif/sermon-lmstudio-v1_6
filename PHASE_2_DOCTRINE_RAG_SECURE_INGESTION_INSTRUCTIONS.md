# Phase 2 작업 지시서 — 공식 자료원 변경 감지·안전한 수집·MinIO 원본 보존

> 선행 문서: DENOMINATION_DOCTRINE_RAG_IMPLEMENTATION_INSTRUCTIONS.md  
> 직전 단계: PHASE_1_DOCTRINE_RAG_DATA_MODEL_INSTRUCTIONS.md  
> 선행 조건: Phase 1 완료 판정 및 마이그레이션·회귀 테스트 통과  
> 이번 범위: 허용목록, SSRF 방어, 조건부 HTTP 수집, 해시 중복 방지, MinIO 원본 보존, 작업 이력  
> 제외 범위: OCR, 본문 구조 분석, 청킹, 임베딩, 실제 RAG 검색, 관리자 완성 UI

---

## 1. Codex 실행 지시

다음 문서와 실제 저장소를 먼저 확인하라.

1. DENOMINATION_DOCTRINE_RAG_IMPLEMENTATION_INSTRUCTIONS.md
2. PHASE_1_DOCTRINE_RAG_DATA_MODEL_INSTRUCTIONS.md
3. Phase 0 기준선 보고서
4. Phase 1 완료 보고서
5. AGENTS.md 및 저장소 지침

이번에는 Phase 2 범위만 구현한다. 기존 일반 RAG, 사용자 업로드, 설교 생성, Provider 연결을 변경하지 않는다. 웹에서 받은 파일을 파싱·OCR·청킹·임베딩하지 말고, 검증된 원본을 안전하게 보존하고 문서 상태를 DOWNLOADED 또는 NEEDS_REVIEW까지 이동시키는 데 그친다.

작업 전 변경 예정 파일, 네트워크 경계, MinIO 저장 정책, 롤백 계획을 보고한다. Phase 1의 실제 테이블·상태·Repository를 재사용하고 비슷한 모델을 중복 생성하지 않는다.

---

## 2. 목표

- 관리자 승인 자료원만 수집
- HTTP/HTTPS URL과 최종 목적지 검증
- 사설망·localhost·클라우드 메타데이터 접근 차단
- ETag와 Last-Modified 기반 조건부 요청
- 스트리밍 다운로드와 크기·시간 제한
- 실제 바이트 SHA-256 계산
- 동일 원본 중복 저장·중복 문서 생성 방지
- 원본과 수집 메타데이터를 MinIO에 판본별 보존
- DB와 객체 저장소의 부분 실패 복구
- 안전한 재시도와 멱등성
- 관리자 검토 전 후속 처리 금지

---

## 3. 구현 전 점검

읽기 전용으로 다음을 확인하고 결과를 기록한다.

- Phase 1 마이그레이션과 테스트 통과 여부
- doctrine_sources, doctrine_documents, source_snapshots, ingestion_jobs 실제 필드
- 기존 HTTP 클라이언트와 보안 래퍼 유무
- 기존 MinIO/S3 클라이언트, 버킷, 접두사, 인증 방식
- 버킷의 versioning, object locking, retention 상태
- MinIO 서버·SDK 버전
- 작업 큐·스케줄러·분산 잠금 유무
- 기존 악성 파일 검사 또는 격리 저장 방식
- 로깅, 감사, 메트릭, 관리자 권한 구현
- 테스트용 MinIO 또는 S3 호환 저장소 유무
- 사용자 미커밋 변경과 파일 충돌

운영 MinIO 설정을 자동 변경하지 않는다. 객체 잠금 지원 여부나 기존 버킷 정책이 불명확하면 저장 정책 변경을 중단하고 호환성 보고만 한다.

---

## 4. 수집 허용 조건

다음 조건을 모두 만족한 자료원만 요청한다.

- source.active = true
- denomination.active = true
- source_authority가 정책상 허용됨
- license_status가 VERIFIED 또는 PUBLIC_DOMAIN
- 관리자가 수집을 명시적으로 활성화함
- URL 호스트가 자료원 허용목록에 등록됨
- 수집 방식이 지원되는 HTML 또는 PDF

UNKNOWN, PERMISSION_REQUIRED, BLOCKED 자료원은 네트워크 요청 전 차단한다. 시드 등록만 된 자료원도 관리자 활성화 전에는 요청하지 않는다.

---

## 5. URL·SSRF 방어

기존 프로젝트의 공통 보안 모듈이 있으면 확장하여 사용한다.

### 허용

- 원칙적으로 HTTPS
- 필요성이 검증된 공식 사이트에 한해 명시적 HTTP 예외
- 등록된 정확한 호스트 또는 승인된 하위 도메인
- 표준 HTTP/HTTPS 포트 또는 자료원별 승인 포트

### 차단

- file, ftp, gopher, data, javascript 및 기타 스킴
- URL 사용자정보 user@host
- localhost와 localhost 하위 표현
- IPv4·IPv6 루프백
- 사설망, 링크 로컬, 멀티캐스트, 예약·미지정 주소
- 클라우드 인스턴스 메타데이터 주소
- 0.0.0.0 및 127.0.0.0/8
- IPv4가 포함된 IPv6 우회 표현
- 10진수·16진수·축약 IP 우회
- 비정상 포트, 제어문자, CRLF
- 허용 호스트처럼 보이는 접미사·사용자정보 혼동 URL

### DNS와 리디렉션

1. URL을 표준 파서로 해석한다.
2. 호스트를 정규화하고 허용목록과 정확히 비교한다.
3. A와 AAAA 결과를 모두 해석해 모든 IP가 허용 범위인지 검사한다.
4. 연결 직전과 가능한 범위에서 실제 연결 대상도 검증한다.
5. 자동 리디렉션을 끄고 한 단계씩 처리한다.
6. 매 리디렉션마다 스킴, 호스트, 포트, DNS/IP를 다시 검사한다.
7. 최대 리디렉션 횟수를 제한한다.
8. 허용되지 않은 다른 호스트로 이동하면 즉시 중단한다.

DNS rebinding에 대비해 검증한 호스트와 실제 연결 대상의 불일치를 허용하지 않는다. 원시 응답·내부 오류·IP 정보를 일반 사용자에게 반환하지 않는다.

---

## 6. HTTP 변경 감지

RFC 9110 의미에 맞게 구현한다.

### 우선순위

1. 이전 ETag가 있으면 If-None-Match
2. ETag가 없고 Last-Modified가 있으면 If-Modified-Since
3. 둘 다 없으면 제한된 GET 후 실제 바이트 해시 비교

서버가 둘 다 제공하면 저장하되 검증 정책을 일관되게 적용한다.

### 응답 처리

- 304: 변경 없음. 새 원본·문서·임베딩을 만들지 않고 확인 시각만 기록
- 200: 스트리밍 수신, 제한 검증, SHA-256 계산
- 206: 전체 문서 수집 정책이 아니면 거부
- 3xx: 수동 리디렉션 검증
- 401/403: 재시도하지 않고 접근 정책 확인 필요
- 404/410: 자료원을 자동 삭제하지 않고 비활성화 검토 상태
- 408/429/5xx: 제한된 지수 백오프 재시도
- 기타: 명시적 실패 코드 기록

HEAD는 최적화 용도로만 사용한다. HEAD가 성공해도 GET 결과의 MIME·크기·해시를 다시 검증한다.

---

## 7. 안전한 다운로드

- 전체 응답을 메모리에 한 번에 올리지 않고 스트리밍 처리
- 연결, 첫 바이트, 읽기, 전체 작업 타임아웃 분리
- 자료원별 최대 파일 크기 적용
- Content-Length가 없어도 실제 수신 바이트 제한
- Content-Length보다 더 큰 응답은 중단
- 압축 해제 후 크기와 압축 비율 제한
- 중첩 압축과 압축폭탄 차단
- 허용 MIME: 정책상 승인한 HTML, PDF와 필요한 텍스트 형식만
- 헤더 MIME, 파일 시그니처, 확장자 교차 확인
- 실행파일·스크립트·위장 파일 거부
- 임시 데이터는 전용 안전 위치에 저장하고 성공·실패 후 정리
- 파일명은 서버 입력을 그대로 경로로 쓰지 않고 내부 생성 키 사용

HTML 안의 이미지, 스크립트, 스타일, iframe, 첨부 링크를 자동으로 따라가지 않는다. PDF 링크 페이지를 수집해야 하면 자료원 설정으로 HTML 본문과 공식 PDF 링크를 구분하고 PDF 목적지도 동일하게 검증한다.

---

## 8. 해시·중복·판본 정책

SHA-256은 다운로드된 실제 원본 바이트로 계산한다.

동일 source_id + content_hash가 이미 있으면:

- MinIO 객체를 다시 저장하지 않는다.
- doctrine_documents 판본을 새로 만들지 않는다.
- source_snapshots에 확인 결과만 기록한다.
- ingestion_job은 NO_CHANGE 또는 기존 상태 체계에 맞는 성공 결과로 종료한다.

해시가 다르면:

- 새 객체 키와 새 문서 판본을 생성한다.
- 이전 판본을 즉시 SUPERSEDED로 바꾸지 않는다.
- 새 문서는 DOWNLOADED 또는 NEEDS_REVIEW로 둔다.
- 관리자가 공식성·판본을 확인한 뒤에만 최신판 관계를 결정한다.

ETag가 바뀌었지만 바이트 해시가 같으면 새 판본을 만들지 않는다. ETag가 같아도 바이트가 다르면 이상 이벤트로 기록하고 새 원본은 검토 대기로 격리한다.

---

## 9. MinIO 원본 보존

권장 객체 키 의미:

doctrine-archive/{denomination_code}/{source_id}/{retrieved_date}/{sha256}/original.{safe_ext}

동일 위치에 다음 메타데이터를 별도 JSON 객체 또는 DB에 보존한다.

- source_id와 denomination_code
- 요청 URL과 최종 승인 URL
- 수집 시각
- HTTP 상태
- ETag와 Last-Modified
- Content-Type과 실제 탐지 MIME
- Content-Length와 실제 크기
- SHA-256
- 수집기 버전
- 이용권한 상태
- 관련 snapshot_id와 ingestion_job_id

원칙:

- 원본 객체는 불변으로 취급
- 같은 키 덮어쓰기 금지
- 버킷 versioning이 가능하면 운영 정책에 따라 사용
- object locking과 retention은 설치 버전·기존 정책 확인 후 별도 승인
- 저장 암호화와 TLS는 기존 보안 설정 재사용
- 로그에 MinIO 비밀키나 서명 URL을 남기지 않음

버전 관리나 잠금 설정 변경은 이번 단계의 코드 배포와 분리한다. 운영 버킷을 즉석에서 잠그지 않는다.

---

## 10. DB·MinIO 정합성과 복구

DB와 객체 저장소는 단일 트랜잭션이 아니므로 보상 흐름을 구현한다.

권장 순서:

1. ingestion_job을 RUNNING으로 생성
2. 안전하게 다운로드하며 해시 계산
3. 중복 확인
4. 임시 객체 키에 업로드
5. 업로드 크기·해시 또는 체크섬 검증
6. 결정적 최종 키로 확정
7. DB snapshot과 document 레코드 트랜잭션 저장
8. 작업 성공 상태 기록

프로젝트의 MinIO SDK가 원자적 rename을 지원한다고 가정하지 않는다. 복사·삭제가 필요한 경우 실패 시 고아 객체를 식별할 수 있게 태그와 작업 ID를 남긴다.

복구 작업은 다음을 탐지해야 한다.

- 객체는 있으나 DB 문서가 없는 고아 객체
- DB에는 있으나 객체가 없는 손상 레코드
- RUNNING 상태로 장시간 남은 작업
- 임시 객체 잔존
- 해시·크기 불일치

자동 복구가 삭제를 수반하면 기본적으로 보고만 하고 관리자 승인 후 처리한다.

---

## 11. 작업 큐·멱등성·재시도

- source_id + 수집 기준시각/버전으로 멱등성 키 생성
- 동일 자료원의 동시 수집 방지
- 다중 프로세스 환경이면 DB 잠금 또는 기존 분산 잠금 사용
- 프로세스 재시작 후 RUNNING 작업 복구 정책 구현
- 429의 Retry-After 존중
- 네트워크 일시 오류와 5xx만 제한 재시도
- 인증 실패, 정책 차단, MIME 불일치, 과대 파일은 자동 재시도 금지
- 최대 시도 횟수와 최대 총 소요시간 적용
- 재처리는 기존 job을 덮어쓰지 않고 parent/retry 관계 기록

운영 스케줄러 등록은 기존 스케줄러가 확인된 경우에만 기능 플래그 뒤에 구현한다. 기본값은 비활성화한다.

---

## 12. 관리·관찰 기능의 최소 범위

완성 UI는 만들지 않되 기존 관리자 인터페이스 방식에 맞춰 최소 조회 기능을 제공할 수 있다.

- 자료원별 마지막 확인 시각
- 변경 없음·신규 원본·실패 상태
- HTTP 결과를 일반화한 오류 코드
- 다운로드 크기·해시
- MinIO 객체 키
- 재시도 횟수
- 정책 차단 이유
- 수동 재검사 요청

원문을 브라우저에 직접 렌더링하지 않는다. HTML 원문 미리보기는 Phase 3 이후 샌드박스·정화 정책과 함께 구현한다.

필수 메트릭:

- 수집 성공/실패/변경 없음 수
- 다운로드 바이트와 소요시간
- 중복 방지 횟수
- SSRF·정책 차단 횟수
- 고아 객체·정합성 오류 수

---

## 13. 테스트

외부 공식 사이트에 반복 요청하지 말고 로컬 모의 HTTP 서버, 저장된 합법적 픽스처, 테스트용 MinIO를 사용한다.

### URL 보안 테스트

- 허용 공식 호스트 성공
- 비허용 호스트 차단
- localhost, 사설 IPv4, IPv6 루프백 차단
- IPv4-mapped IPv6 차단
- 10진수·16진수 IP 우회 차단
- userinfo와 호스트 접미사 혼동 차단
- CRLF·제어문자 차단
- DNS가 사설 IP를 반환하면 차단
- 리디렉션이 사설망 또는 비허용 호스트로 이동하면 차단
- 리디렉션 횟수 초과 차단

### HTTP 테스트

- ETag + If-None-Match → 304
- Last-Modified + If-Modified-Since → 304
- 검증자 없음 → 해시 비교
- HEAD 미지원 후 안전한 GET
- 200·304·3xx·401·403·404·410·429·5xx 처리
- Retry-After 및 재시도 상한
- 연결·읽기·전체 타임아웃

### 파일 안전 테스트

- 허용 HTML/PDF
- MIME 위장 파일
- Content-Length 초과
- 실제 스트림 크기 초과
- 압축폭탄과 중첩 압축
- 비정상 파일명과 경로 순회
- 중간 연결 종료
- 해시 계산 정확성

### 저장·정합성 테스트

- 새 원본 업로드와 DB 기록
- 동일 해시 재수집 시 객체·문서 중복 0건
- 변경 해시 새 판본 생성
- MinIO 업로드 실패 시 DB 오염 없음
- DB 커밋 실패 시 고아 객체 식별 가능
- 객체 체크섬 불일치 시 승인 경로 진입 금지
- 장시간 RUNNING 작업 복구
- 동시에 같은 자료원을 실행해도 1회만 처리

### 회귀 테스트

- Phase 1 모델·마이그레이션 테스트
- 기존 일반 RAG
- 기존 사용자 파일 업로드
- 기존 설교 생성
- MinIO 기존 객체 읽기

---

## 14. 기능 플래그와 설정

설정명은 기존 규칙에 맞춘다.

- 교단 자료원 수집 기능: 기본 OFF
- 예약 수집: 기본 OFF
- 수동 관리자 수집: 테스트 후 선택적 ON
- 최대 파일 크기
- 연결·읽기·전체 타임아웃
- 최대 리디렉션
- 최대 재시도
- 허용 MIME
- 버킷과 객체 접두사

환경변수 예시 값을 실제 비밀값으로 문서에 넣지 않는다. 잘못된 설정은 안전하게 실패해야 하며 일반 RAG를 중단시키지 않는다.

---

## 15. 완료 조건

- [ ] Phase 1 완료와 회귀 테스트를 재확인함
- [ ] 승인·활성 자료원만 요청함
- [ ] 스킴·호스트·포트·DNS/IP·리디렉션을 모두 검증함
- [ ] 사설망·localhost·메타데이터 주소 접근이 차단됨
- [ ] ETag/Last-Modified 조건부 요청과 304가 구현됨
- [ ] 스트리밍·크기·시간·MIME 제한이 구현됨
- [ ] SHA-256 기반 중복 방지가 DB와 MinIO 모두에서 동작함
- [ ] 과거 판본을 덮어쓰지 않음
- [ ] 새 문서는 승인 전 상태로만 저장됨
- [ ] DB·MinIO 부분 실패를 탐지·복구할 수 있음
- [ ] 자동 수집 기능의 기본값이 OFF임
- [ ] 실제 교단 사이트를 테스트 부하 대상으로 쓰지 않음
- [ ] OCR·청킹·임베딩을 구현하지 않음
- [ ] 기존 일반 RAG·업로드·설교 생성 회귀 테스트 통과

하나라도 실패하면 Phase 2 완료로 표시하지 않는다.

---

## 16. 중단 조건

- Phase 1이 완료되지 않았거나 마이그레이션 체인이 불안정함
- 안전한 테스트 DB 또는 테스트 MinIO가 없음
- 기존 MinIO 정책 변경이 필수이나 승인받지 않음
- URL 검증 후 실제 연결 IP를 통제할 방법이 없음
- HTTP 클라이언트가 자동 리디렉션을 안전하게 제어할 수 없음
- 다운로드 상한을 스트리밍 단계에서 강제할 수 없음
- 사용자 미커밋 변경과 충돌함
- 운영 자격증명 또는 이용 허가가 불명확함

중단 시 우회하지 말고 원인, 영향, 안전한 해결 선택지를 보고한다.

---

## 17. 롤백

- 교단 자동 수집 기능 플래그 OFF
- 예약 작업 중지
- 새 코드 경로 비활성화 후 기존 일반 RAG 유지
- Phase 2에서 생성된 미승인 문서만 식별
- 객체 삭제는 자동 실행하지 말고 목록과 해시를 관리자에게 보고
- DB 롤백은 Phase 1 테이블을 제거하지 않음
- 기존 MinIO 버킷 정책을 원래 상태로 임의 변경하지 않음

---

## 18. 최종 보고 형식

1. 구현 결과
2. 변경 파일과 역할
3. URL·SSRF 방어 방법
4. HTTP 변경 감지 규칙
5. 다운로드 제한값과 설정 위치
6. MinIO 저장 키·버전 정책
7. DB·MinIO 정합성 및 복구 방법
8. 실행한 보안·통합·회귀 테스트와 실제 결과
9. 미해결 위험과 제한
10. 기능 플래그와 롤백 방법
11. Phase 3 본문 추출·OCR 단계로 넘길 인터페이스

최종 판정은 하나만 사용한다.

- Phase 2 완료 — Phase 3 진행 가능
- 조건부 완료 — 보완 후 Phase 3 가능
- Phase 2 중단 — 원인 해결 필요

---

## 19. 공식 기술 근거

- [RFC 9110 — HTTP Semantics와 조건부 요청](https://www.rfc-editor.org/rfc/rfc9110)
- [OWASP — Server-Side Request Forgery Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP — Input Validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [MinIO — Object Versioning](https://docs.min.io/aistor/administration/objects-and-versioning/versioning/enable-versioning/)
- [MinIO — Object Locking and Immutability](https://docs.min.io/aistor/administration/object-locking-and-immutability/)

