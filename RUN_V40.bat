@echo off
setlocal
cd /d "%~dp0"
for /f "usebackq delims=" %%V in ("VERSION.txt") do if not defined EXPECTED_VERSION set "EXPECTED_VERSION=%%V"

if not exist "VERSION.txt" (
  echo [ERROR] VERSION.txt is missing.
  echo This is not a complete versioned package. Restore VERSION.txt from the current release.
  pause
  exit /b 7
)

set /p PACKAGE_VERSION=<"VERSION.txt"
if not "%PACKAGE_VERSION%"=="%EXPECTED_VERSION%" (
  echo [ERROR] Wrong package version: V%PACKAGE_VERSION%
  echo Expected V%EXPECTED_VERSION%.
  echo Use the launcher and executable from the same release folder.
  pause
  exit /b 8
)

echo Sermon LM Studio V%PACKAGE_VERSION% package verified.
call start.bat
exit /b %ERRORLEVEL%
