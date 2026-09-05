param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

# Windows 작업 스케줄러에서 이 스크립트를 호출하면 KMC 공식 URL의
# HEAD 메타데이터만 확인합니다. 응답 본문·원문 파일은 읽지 않습니다.
$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "가상환경 Python을 찾지 못했습니다: $python"
}

Push-Location $ProjectRoot
try {
    & $python -c "from app.kmc_reference import probe_kmc_reference_headers; from app.core import DB_PATH; import json; print(json.dumps(probe_kmc_reference_headers(DB_PATH), ensure_ascii=False))"
    if ($LASTEXITCODE -ne 0) { throw "KMC HEAD 점검이 실패했습니다. 종료 코드: $LASTEXITCODE" }
}
finally {
    Pop-Location
}

# 작업 스케줄러 등록 예시(관리자 승인 후 수동 등록):
# powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_kmc_reference.ps1
