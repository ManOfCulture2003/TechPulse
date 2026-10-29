@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  py -3 launch.py
) else (
  python launch.py
)
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
  echo.
  echo [TechPulse] See the message above for troubleshooting.
  pause
)
exit /b %RESULT%
