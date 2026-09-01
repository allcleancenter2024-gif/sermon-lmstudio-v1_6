# 한글 폰트 배치 안내

폰트 바이너리는 프로젝트에 임의 재배포하지 않습니다. 아래 파일을 각 폰트의 공식 배포처/라이선스를 확인한 뒤 이 폴더에 넣으면 프로그램이 자동 사용합니다.

## 대시보드 HTML - S-Core Dream

- `S-CoreDream-3Light.woff2`
- `S-CoreDream-5Medium.woff2`
- `S-CoreDream-6Bold.woff2`

같은 이름의 `.ttf` 파일도 인식합니다. 폰트 자체를 변환할 필요는 없으며 공식 배포본에서 제공되는 형식을 그대로 사용하는 것을 권장합니다.

대시보드 HTML은 `@font-face`를 사용합니다. 위 파일이 있으면 내보낸 단일 HTML 안에 base64로 포함해 다른 PC에서도 같은 글꼴로 보이게 합니다. 파일이 없으면 시스템의 `S-Core Dream`을 찾고, 이어서 `Noto Sans KR`, sans-serif로 fallback합니다.

공식 S-Core 글꼴 페이지: https://s-core.co.kr/company/font/

## PDF - NanumSquare / NanumGothic

- `NanumSquareR.ttf`
- `NanumSquareB.ttf`
- `NanumGothic.ttf`
- `NanumGothicBold.ttf`

PDF는 외부 CDN에 의존하지 않습니다. WeasyPrint가 위 로컬 TTF를 `@font-face`로 읽도록 하며, 파일이 없으면 시스템에 설치된 NanumSquare -> NanumGothic -> Noto Sans KR 순서로 fallback합니다.

## 웹 앱 - Pretendard

웹 앱은 Pretendard 공식 프로젝트가 안내하는 jsDelivr `Pretendard Variable` dynamic subset을 사용합니다. 인터넷이 끊기면 로컬 `Pretendard`, `Noto Sans KR`, 시스템 sans-serif 순서로 fallback합니다.
