# 초기 관리자 계정 생성

로그인 화면의 초기 계정 생성 기능을 사용할 수 없는 경우, 프로젝트 폴더의 `CREATE_INITIAL_ACCOUNT.bat` 또는 `create_initial_account.py`를 사용합니다.

## Windows 권장 방법

1. 프로그램을 종료합니다.
2. 소스/개발 실행이면 `CREATE_INITIAL_ACCOUNT.bat`, 빌드된 EXE 로그인용이면 `CREATE_INITIAL_ACCOUNT_EXE.bat`를 실행합니다.
3. 사용자명과 10자 이상의 비밀번호를 입력합니다.
4. 생성 후 프로그램을 다시 실행하고 로그인합니다.

실행 방식에 따라 인증 DB 위치가 다릅니다. 소스/개발 실행은 프로젝트 폴더의 `auth.sqlite3`를 사용하고, 빌드된 EXE는 사용자 데이터 폴더의 DB를 사용합니다.

```text
C:\Users\<사용자명>\AppData\Local\SermonLMStudio\auth.sqlite3
```

빌드된 EXE의 초기 계정을 만들 때는 다음처럼 EXE가 사용하는 DB를 명시하세요.

```powershell
python create_initial_account.py --db "C:\경로\auth.sqlite3"
```

PowerShell에서는 다음과 같이 실행할 수 있습니다.

```powershell
python create_initial_account.py --db "$env:LOCALAPPDATA\SermonLMStudio\auth.sqlite3"
```

사용자명을 명령줄에서 지정할 수도 있지만 비밀번호는 명령줄 인자로 전달하지 않습니다.

```powershell
python create_initial_account.py --username pastor
```

## 안전 규칙

- 이미 계정이 하나라도 있으면 파일은 중단하며 기존 계정을 덮어쓰지 않습니다.
- 첫 계정은 `admin` 역할로 생성됩니다.
- 비밀번호는 PBKDF2-SHA256 해시와 임의 salt로 저장되며 평문으로 저장하지 않습니다.
- 인증 DB는 설교 본문 DB와 분리되어 있습니다.
- 비밀번호를 잊은 경우 DB 파일을 임의로 삭제하지 말고, 기존 백업과 운영자 승인 절차를 먼저 확인합니다.

## 기존 계정 교체

기존 계정을 새 ID와 비밀번호로 교체해야 할 때만 다음 파일을 사용합니다.

- 개발/소스 실행: `REPLACE_INITIAL_ACCOUNT.bat`
- 빌드된 EXE: `REPLACE_INITIAL_ACCOUNT_EXE.bat`

이 파일은 기존 인증 DB를 `.pre-replace-날짜시간.bak`으로 백업한 뒤, `REPLACE`를 직접 입력한 경우에만 기존 계정을 모두 제거하고 새 관리자 계정 하나를 생성합니다. 백업 생성이나 확인이 실패하면 DB를 변경하지 않습니다.
