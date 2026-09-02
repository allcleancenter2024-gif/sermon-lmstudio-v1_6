@echo off
setlocal
cd /d "%~dp0"
set "EXPECTED_VERSION=40.9.10"

echo [1/4] Checking Python virtual environment...
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  py -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create the Python virtual environment.
    echo Install Python 3.11 or newer and make sure the "py" command is available.
    pause
    exit /b 1
  )
)

echo [2/4] Checking required packages...
".venv\Scripts\python.exe" verify_dependencies.py --check >nul 2>&1
if errorlevel 1 (
  echo Installing required packages for the first run or an update...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-pdf.txt
  if errorlevel 1 (
    echo [ERROR] Python package installation failed.
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" verify_dependencies.py --write
  if errorlevel 1 (
    echo [ERROR] Required package verification failed after installation.
    pause
    exit /b 1
  )
) else (
  echo Required packages are already ready. Skipping pip installation.
)

echo [3/4] Verifying application import and package version...
".venv\Scripts\python.exe" verify_version.py "%EXPECTED_VERSION%"
set "VERIFY_EXIT=%ERRORLEVEL%"
if "%VERIFY_EXIT%"=="6" (
  echo.
  echo [ERROR] This folder contains a different application version.
  echo Extract SermonLMStudio-V40.9.2 into a NEW empty folder.
  pause
  exit /b 6
)
if not "%VERIFY_EXIT%"=="0" (
  echo.
  echo [ERROR] The application could not be loaded or verified.
  echo The detailed Python error is shown above. Please copy it when asking for help.
  pause
  exit /b %VERIFY_EXIT%
)

echo [4/4] Starting unified sermon launcher V%EXPECTED_VERSION%...
echo Web Grounding default: OFF (set WEB_GROUNDING_ENABLED=true only for approved evaluations)
".venv\Scripts\python.exe" launcher.py
set "LAUNCHER_EXIT=%ERRORLEVEL%"
if not "%LAUNCHER_EXIT%"=="0" (
  echo.
  echo Launcher stopped with exit code %LAUNCHER_EXIT%.
  pause
)
exit /b %LAUNCHER_EXIT%
