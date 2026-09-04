param([switch]$Apply)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $Root

git rev-parse --show-toplevel | Out-Null
$status = @(git status --short)
$head = (git rev-parse --short HEAD).Trim()
Write-Host "정상 기준 커밋: $head"
if ($status.Count -eq 0) {
    Write-Host '현재 작업 트리가 이미 정상 기준 상태입니다.'
    exit 0
}

Write-Host "복구 대상 추적 파일: $($status.Count)개 변경 항목"
if (-not $Apply) {
    Write-Host '미리보기만 수행했습니다. 실제 복구는 -Apply를 붙여 실행하세요.'
    git status --short
    exit 0
}

$recoveryDir = Join-Path $Root 'backups\recovery'
New-Item -ItemType Directory -Force -Path $recoveryDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$patchPath = Join-Path $recoveryDir "before_restore_$stamp.patch"
git diff --binary | Out-File -LiteralPath $patchPath -Encoding utf8
git diff --cached --binary | Out-File -LiteralPath (Join-Path $recoveryDir "before_restore_$stamp.staged.patch") -Encoding utf8

# HEAD 기준으로 추적 파일만 복구한다. 사용자 데이터와 미추적 파일은 건드리지 않는다.
git restore --source HEAD --worktree --staged -- .
Write-Host "복구 완료: $head"
Write-Host "복구 전 변경사항 보관: $patchPath"
Write-Host '미추적 사용자 파일은 삭제하지 않았습니다.'
