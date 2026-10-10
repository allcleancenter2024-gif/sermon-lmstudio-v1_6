@echo off
setlocal
cd /d "%~dp0"

for /f "usebackq delims=" %%V in ("%~dp0..\..\VERSION.txt") do if not defined EXPECTED_VERSION set "EXPECTED_VERSION=%%V"
if not defined EXPECTED_VERSION (
  echo [ERROR] The canonical VERSION.txt was not found.
  pause
  exit /b 9
)

if not defined SERMON_USER_ROOT set "SERMON_USER_ROOT=%~dp0..\.."
set "APP_EXE=%~dp0SermonLMStudio_V%EXPECTED_VERSION%.exe"
if not exist "%APP_EXE%" (
  echo [ERROR] The canonical V%EXPECTED_VERSION% executable is missing.
  echo Rebuild it from the project root with build_windows.bat.
  pause
  exit /b 2
)

echo Sermon LM Studio V%EXPECTED_VERSION%
echo User data: %SERMON_USER_ROOT%
echo LM Studio: http://127.0.0.1:12345/v1
echo Keep this window open while using the program.
"%APP_EXE%"
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" (
  echo The program closed with exit code %APP_EXIT%.
  pause
)
exit /b %APP_EXIT%
