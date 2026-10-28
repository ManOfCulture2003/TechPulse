@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)
if not exist ".venv\Scripts\python.exe" (
  echo [TechPulse] Creating your local Python environment...
  %PY% -m venv .venv
  if errorlevel 1 goto :failed
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :failed
)
echo.
echo [TechPulse] Visit http://127.0.0.1:8765 in your browser.
echo [TechPulse] Press Ctrl+C to stop monitoring.
start "" "http://127.0.0.1:8765"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8765
pause
exit /b 0
:failed
echo [TechPulse] Setup failed. Make sure Python 3.11+ is installed with PATH access.
pause
exit /b 1
