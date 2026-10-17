$ErrorActionPreference = "Stop"
$Python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (!(Test-Path $Python)) { throw "OmniForge virtual environment not found. Run Setup-OmniForge.bat first." }
& $Python -m pip install -r requirements-motion.txt
if ($LASTEXITCODE -ne 0) { throw "Optional motion-capture dependencies failed to install." }
Write-Host "Optional local motion capture dependencies installed. Restart OmniForge and use the Video Motion Capture panel."
