param([string]$RemoteUrl = "")

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
if (Test-Path -LiteralPath (Join-Path $projectRoot ".git")) {
    throw "이미 Git 저장소입니다. 기존 저장소를 덮어쓰지 않고 중단합니다."
}

& git init --initial-branch=main $projectRoot
if ($LASTEXITCODE -ne 0) { throw "Git 저장소 초기화에 실패했습니다." }
if ($RemoteUrl) {
    & git remote add origin $RemoteUrl
    if ($LASTEXITCODE -ne 0) { throw "원격 주소 등록에 실패했습니다. 로컬 저장소는 초기화되었습니다." }
}
Write-Host "로컬 Git 저장소를 초기화했습니다. commit/push는 실행하지 않았습니다."
