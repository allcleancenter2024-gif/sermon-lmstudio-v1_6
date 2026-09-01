# V40.9.1 Qwen 스트리밍 수정 롤백

V40.9.1은 3대지 생성의 출력 제한과 Qwen reasoning 스트림 처리만 변경합니다. DB 구조는 변경하지 않습니다.

1. 프로그램과 LM Studio 생성 작업을 종료합니다.
2. 현재 폴더 이름을 `V40.9.1-보관`으로 변경합니다.
3. `SermonLMStudio-V40.9.0-FIXED19-Streaming.zip`을 새 빈 폴더에 풉니다.
4. LM Studio 포트 `12345`는 그대로 유지합니다.
