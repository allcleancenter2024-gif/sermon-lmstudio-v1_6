@echo off
setlocal
cd /d "%~dp0"

set "EXPECTED_VERSION=40.9.10"

echo [1/7] Preparing clean Windows build environment...
if not exist ".build-venv\Scripts\python.exe" (
  py -3.11 -m venv .build-venv 2>nul
  if errorlevel 1 py -m venv .build-venv
)
if not exist ".build-venv\Scripts\python.exe" (
  echo [ERROR] Python 3.11 or newer is required.
  pause
  exit /b 1
)
".build-venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
  echo [ERROR] Python 3.11 or newer is required for the Windows build.
  pause
  exit /b 1
)

echo [2/7] Installing application and EXE build packages...
".build-venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-pdf.txt -r requirements-build.txt
if errorlevel 1 goto :build_error

echo [3/7] Running compile and regression checks before packaging...
".build-venv\Scripts\python.exe" -m compileall -q app scripts
if errorlevel 1 goto :build_error
if not exist ".pytest-build" mkdir ".pytest-build"
".build-venv\Scripts\python.exe" -m pytest -q --basetemp=".pytest-build"
if errorlevel 1 goto :build_error

echo [4/7] Checking Windows PDF engine and Korean font...
".build-venv\Scripts\python.exe" -c "from app.exporters import pdf_environment_status; s=pdf_environment_status(); print('[INFO] PDF: '+str(s.get('engine'))+' / '+str(s.get('font_family'))); raise SystemExit(0 if s.get('ready') else 1)"
if errorlevel 1 (
  echo [ERROR] ReportLab or a usable Korean font is missing. Install Malgun Gothic or place an approved Nanum TTF in fonts.
  goto :build_error
)

echo [5/7] Building SermonLMStudio.exe...
if exist "dist\SermonLMStudio.exe" del /q "dist\SermonLMStudio.exe"
".build-venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --console --name SermonLMStudio --collect-all uvicorn --collect-all reportlab --exclude-module weasyprint --hidden-import app.providers.web --add-data "templates;templates" --add-data "static;static" --add-data "fonts;fonts" launcher.py
if errorlevel 1 goto :build_error

echo [6/7] Verifying EXE and application version...
if not exist "dist\SermonLMStudio.exe" goto :build_error
"dist\SermonLMStudio.exe" --version > ".built-version.tmp"
if errorlevel 1 goto :build_error
set /p BUILT_VERSION=<".built-version.tmp"
del /q ".built-version.tmp" 2>nul
if not "%BUILT_VERSION%"=="%EXPECTED_VERSION%" (
  echo [ERROR] EXE version mismatch. Expected %EXPECTED_VERSION%, got %BUILT_VERSION%.
  goto :build_error
)

echo [7/7] Complete.
echo EXE: %CD%\dist\SermonLMStudio.exe
echo Run LM Studio, start Developer / Local Server, then double-click this EXE.
echo For a command-line readiness report, run: dist\SermonLMStudio.exe --diagnose
pause
exit /b 0

:build_error
echo.
echo [ERROR] Windows EXE build failed. Copy the error shown above when asking for help.
pause
exit /b 1
