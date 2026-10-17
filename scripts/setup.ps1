$ErrorActionPreference = "Stop"
py -3 -m venv .venv
if (!(Test-Path ".env")) { Copy-Item ".env.example" ".env" }
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
Write-Host "Setup complete. Configure .env, then run .\scripts\run.ps1"
