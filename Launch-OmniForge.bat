@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo OmniForge is not installed yet. Run Setup-OmniForge.bat first.
  pause
  exit /b 1
)
"%CD%\.venv\Scripts\python.exe" -m app.desktop
