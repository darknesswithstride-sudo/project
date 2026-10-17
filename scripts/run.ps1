$ErrorActionPreference = "Stop"
if (!(Test-Path ".venv\Scripts\python.exe")) { throw "Run .\scripts\setup.ps1 first." }
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
