param(
    [Parameter(Mandatory = $true)][string]$Message,
    [string]$RemoteUrl = "https://github.com/allcleancenter2024-gif/sermon-lmstudio-v1_6.git",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
& git remote set-url origin $RemoteUrl
if ($LASTEXITCODE -ne 0) { throw "origin 원격 주소 설정에 실패했습니다." }
& git add -A
if ($LASTEXITCODE -ne 0) { throw "변경사항 스테이징에 실패했습니다." }
& git commit -m $Message
if ($LASTEXITCODE -ne 0) { throw "커밋에 실패했거나 커밋할 변경사항이 없습니다." }
& git push -u origin $Branch
if ($LASTEXITCODE -ne 0) { throw "push에 실패했습니다. 인증·원격 상태를 확인하세요." }
