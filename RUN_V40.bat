@echo off
setlocal
cd /d "%~dp0"
set "EXPECTED_VERSION=40.9.10"

if not exist "VERSION.txt" (
  echo [ERROR] VERSION.txt is missing.
  echo This is not a complete V40 package. Extract the new V40 ZIP again.
  pause
  exit /b 7
)

set /p PACKAGE_VERSION=<"VERSION.txt"
if not "%PACKAGE_VERSION%"=="%EXPECTED_VERSION%" (
  echo [ERROR] Wrong package version: V%PACKAGE_VERSION%
  echo Expected V%EXPECTED_VERSION%.
  echo Use the newly downloaded SermonLMStudio-V40-FIXED12 package.
  pause
  exit /b 8
)

echo Sermon LM Studio V%PACKAGE_VERSION% package verified.
call start.bat
exit /b %ERRORLEVEL%
