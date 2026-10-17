@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher was not found. Install Python 3.11 or newer from https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
py -3 -m venv .venv
if errorlevel 1 goto fail
if not exist .env copy .env.example .env
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo.
echo Setup complete. Read README.md, install free local tools as needed, then run Launch-OmniForge.bat.
pause
exit /b 0
:fail
echo Setup failed. Read the error above and check Python and internet access.
pause
exit /b 1
