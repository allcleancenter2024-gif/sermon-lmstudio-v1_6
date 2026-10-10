@echo off
setlocal
cd /d "%~dp0"

for /f "usebackq delims=" %%V in ("VERSION.txt") do if not defined EXPECTED_VERSION set "EXPECTED_VERSION=%%V"
if not defined EXPECTED_VERSION (
  echo [ERROR] VERSION.txt is missing or empty.
  pause
  exit /b 9
)
set "BUILD_ARTIFACT=SermonLMStudio_V%EXPECTED_VERSION%"
set "BUILD_CANDIDATE=SermonLMStudio_V%EXPECTED_VERSION%_candidate"
set "RELEASE_DIR=release\V%EXPECTED_VERSION%"
set "BUILD_WORK=.pyinstaller-work-release-%EXPECTED_VERSION%"
set "PYTEST_TEMP=.pytest-release-%EXPECTED_VERSION%"
if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"

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
if not exist "%PYTEST_TEMP%" mkdir "%PYTEST_TEMP%"
".build-venv\Scripts\python.exe" -m pytest -q --basetemp="%PYTEST_TEMP%"
if errorlevel 1 goto :build_error

echo [4/7] Checking Windows PDF engine and Korean font...
".build-venv\Scripts\python.exe" -c "from app.exporters import pdf_environment_status; s=pdf_environment_status(); print('[INFO] PDF: '+str(s.get('engine'))+' / '+str(s.get('font_family'))); raise SystemExit(0 if s.get('ready') else 1)"
if errorlevel 1 (
  echo [ERROR] ReportLab or a usable Korean font is missing. Install Malgun Gothic or place an approved Nanum TTF in fonts.
  goto :build_error
)

echo [5/7] Building SermonLMStudio.exe...
if exist "%RELEASE_DIR%\%BUILD_CANDIDATE%.exe" del /q "%RELEASE_DIR%\%BUILD_CANDIDATE%.exe"
".build-venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --console --name "%BUILD_CANDIDATE%" --workpath "%BUILD_WORK%" --specpath "%BUILD_WORK%" --distpath "%RELEASE_DIR%" --runtime-tmpdir ".build-tmp" --collect-all uvicorn --collect-all reportlab --exclude-module weasyprint --hidden-import app.providers.web --add-data "%CD%\templates;templates" --add-data "%CD%\static;static" --add-data "%CD%\fonts;fonts" --add-data "%CD%\app\assets\hwpx_base;app\assets\hwpx_base" --add-data "%CD%\VERSION.txt;." launcher.py
if errorlevel 1 goto :build_error

echo [6/7] Verifying EXE and application version...
if not exist "%RELEASE_DIR%\%BUILD_CANDIDATE%.exe" goto :build_error
"%RELEASE_DIR%\%BUILD_CANDIDATE%.exe" --version > ".built-version.tmp"
if errorlevel 1 goto :build_error
set /p BUILT_VERSION=<".built-version.tmp"
del /q ".built-version.tmp" 2>nul
if not "%BUILT_VERSION%"=="%EXPECTED_VERSION%" (
  echo [ERROR] EXE version mismatch. Expected %EXPECTED_VERSION%, got %BUILT_VERSION%.
  goto :build_error
)

move /y "%RELEASE_DIR%\%BUILD_CANDIDATE%.exe" "%RELEASE_DIR%\%BUILD_ARTIFACT%.exe" >nul
if errorlevel 1 goto :build_error

echo [7/7] Complete.
echo EXE: %CD%\%RELEASE_DIR%\%BUILD_ARTIFACT%.exe
echo Run: %CD%\%RELEASE_DIR%\RUN_SermonLMStudio.bat
echo Start the LM Studio local server before opening the app.
echo For a command-line readiness report, run: %RELEASE_DIR%\%BUILD_ARTIFACT%.exe --diagnose
pause
exit /b 0

:build_error
echo.
echo [ERROR] Windows EXE build failed. Copy the error shown above when asking for help.
pause
exit /b 1
