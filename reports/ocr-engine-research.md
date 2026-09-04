# OCR 엔진 후보 조사 보고서

작성일: 2026-09-04

## 결론

현재 프로젝트에는 OCR 엔진을 자동 설치하거나 기본 활성화하지 않는다. 다음 구현 단계에서
검증된 Windows 실행 경로를 설정으로 주입할 수 있는 Tesseract 어댑터를 선택 후보로 둔다.

## 후보 비교

| 후보 | 장점 | 위험·제약 | 현재 판단 |
|---|---|---|---|
| Tesseract 5 + pytesseract | Apache-2.0 엔진과 Apache-2.0 Python wrapper, 로컬 실행, `heb`·`grc` 언어 데이터 제공 | 최신 Windows 설치파일은 공식 배포 경계가 약하고, 스캔 PDF는 별도 렌더링 계층이 필요 | 1순위 후보 |
| OCRmyPDF | 스캔 PDF에 검색 가능한 텍스트 레이어를 만들 수 있고 Tesseract 연계가 명확함 | Tesseract 외 Ghostscript·qpdf 등 OS 의존성이 추가됨; 원본 보존과 임시파일 격리가 필요 | 보조 오케스트레이터 후보 |
| PaddleOCR | Apache-2.0 프로젝트, 복잡한 문서 레이아웃 확장 가능 | Python·모델·GPU/CPU 런타임이 무겁고 개별 모델 및 배포물 라이선스 확인 필요 | 현재 보류 |

## 성경 원어 언어 정책

- 히브리어: `heb`
- 고대 그리스어: `grc`
- 현대 그리스어가 필요한 별도 자료: `ell`
- OCR 결과는 확정 성경 근거로 자동 승격하지 않고, confidence·페이지 수·본문 대조를 통과한
  검토 대기 자료로만 보관한다.

## 다음 구현 경계

1. 실행 파일 경로와 `tessdata` 경로를 환경설정으로만 받는다.
2. 허용된 임시 작업 디렉터리에서만 PDF를 처리한다.
3. subprocess 인자는 배열로 전달하고 shell 실행은 금지한다.
4. 원본 PDF의 SHA-256과 OCR 결과의 SHA-256을 각각 기록한다.
5. `heb`·`grc` 샘플 fixture로 페이지 수, 비어 있지 않은 본문, confidence 임계값,
   원본 불변성을 검증한다.
6. 실패·낮은 confidence·언어 데이터 누락은 색인/근거 승격 없이 검토 상태로 종료한다.

## 현재 환경 readiness 점검

2026-09-04 점검 결과 PATH에서 `tesseract` 실행파일을 찾지 못했다. 따라서 실제 OCR은
실행하지 않았으며, 프로그램에는 설치 없이 상태를 보고하는 `check_tesseract_readiness()`가
추가되었다. 실행파일이 없거나 `heb`·`grc` 언어 데이터가 없으면 OCR을 사용할 수 없는
상태로 보고한다.

## 설치 시도 결과

사용자 승인으로 Chocolatey 저장소의 `tesseract 5.5.3.20260724` 패키지를 확인하고 설치를
시도했으나, 현재 셸이 관리자 권한이 아니어서 Chocolatey 전역 경로
`C:\\ProgramData\\chocolatey\\lib`의 lock 파일 및 `lib-bad` 경로에 접근하지 못했다.
설치는 완료되지 않았으며 Tesseract 바이너리는 설치되지 않았다. 잠금 파일 삭제나 권한
우회는 수행하지 않았다.

## 원어 데이터 설치 시도 결과

공식 `tessdata_best` 저장소에서 다음 파일을 다운로드하고 SHA-256을 확인했다.

| 파일 | SHA-256 | 설치 결과 |
|---|---|---|
| `heb.traineddata` | `DBAA827AEA6BC21215638447F17783A1004987C2D0BF5573D111FEE397ABDAE5` | 관리자 권한 부족으로 복사 보류 |
| `grc.traineddata` | `DFC9BDA286CD9D8755B1832E5731A5425D1CF0803393A5FA6DEE078466178CF1` | 관리자 권한 부족으로 복사 보류 |

다운로드 파일은 `C:\\Users\\Home_care\\Downloads\\tesseract-language-data-v5.5.3`에
보관되어 있다. Tesseract 설치 폴더에는 복사되지 않았고, 현재 `--list-langs`에는 여전히
`eng`, `kor`, `osd`만 표시된다.

## 라이선스 기록

- Tesseract engine: Apache License 2.0
- pytesseract: Apache License 2.0
- OCRmyPDF: MPL-2.0; 수정 시 OCRmyPDF 자체 수정사항 공개 의무를 검토한다.
- PaddleOCR: Apache-2.0 프로젝트이나 모델·부속 파일별 고지를 별도 확인한다.

## 조사 출처

- https://tesseract-ocr.github.io/tessdoc/Installation.html
- https://tesseract-ocr.github.io/tessdoc/supported-operating-systems.html
- https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE
- https://github.com/tesseract-ocr/tesseract/blob/main/doc/tesseract.1.asc
- https://github.com/madmaze/pytesseract
- https://github.com/ocrmypdf/OCRmyPDF
- https://ocrmypdf.readthedocs.io/en/latest/installation.html
- https://github.com/PaddlePaddle/PaddleOCR

## 실제 원어 fixture 검증 결과

`heb`와 `grc` 언어 데이터가 설치된 뒤 임시 PNG fixture로 실제 OCR을 실행했다.

- 히브리어: confidence `0.193`, 인식 결과가 원문과 불일치하여 기준 `0.85` 미달
- 고대 그리스어(GraecaII): confidence `0.751`, 인식 결과 불일치
- 고대 그리스어(SILEOT): confidence `0.603`, 인식 결과 불일치
- 각 fixture 원본은 OCR 과정 전후 SHA-256 불변성을 확인했으며 DB·MinIO에는 등록하지 않았다.

결론적으로 언어 데이터 설치는 성공했지만, 현재 fixture의 OCR 품질은 설교 근거 승격 기준을
통과하지 못했다. 실제 자료 적용 전 스캔 해상도, 글꼴, 전처리, 페이지 분할 및 사람 검수
절차를 추가로 검증해야 한다.

## 구조적 해결 확인

고대 그리스어 신약 원문은 OCR로 복원하지 않고 이미 설치·검증된 SBLGNT를 정본으로
사용한다. `JHN 1:1`을 기존 `greek_text` Repository에서 조회한 결과 SBLGNT 원문은
`Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος.`로 확인되었고,
MorphGNT에는 동일 구절의 표면형·lemma·형태 정보가 존재한다.

따라서 정책을 다음처럼 확정한다.

- SBLGNT/MorphGNT가 있는 신약 원어 본문: 정본 텍스트를 사용하고 OCR을 사용하지 않는다.
- 스캔 문서에서만 OCR을 보조적으로 사용한다.
- OCR 결과가 원어 정본과 불일치하면 자동 근거·RAG 색인에 사용하지 않는다.
- OCR confidence 기준 `0.85`는 유지한다.
