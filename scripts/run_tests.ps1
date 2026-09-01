param([Parameter(ValueFromRemainingArguments = $true)][string[]]$PytestArgs)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw ".venv가 없습니다. start.bat을 먼저 실행하거나 Python 가상환경을 만드세요." }
$runRoot = Join-Path $projectRoot ".test-runs"
New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
$runDir = Join-Path $runRoot ("pytest-" + (Get-Date -Format "yyyyMMdd-HHmmss-fff"))
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
& $python -m pytest "--basetemp=$runDir" @PytestArgs
exit $LASTEXITCODE
