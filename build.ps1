# One-click build for AnimeList_v4.4 (Windows / PowerShell)
# Usage: .\build.ps1
# Output: dist\AnimeList_v4.exe

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$py = Join-Path $here '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    throw "Virtual environment .venv not found. Run: python -m venv .venv"
}

& $py -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }

& $py -m PyInstaller --clean --noconfirm --onefile --noconsole `
    --name AnimeList_v4 `
    --icon bgm.ico `
    --add-data "index.html;." `
    main.py
if ($LASTEXITCODE -ne 0) { throw "Build failed" }

Write-Host ""
Write-Host "Build complete: $here\dist\AnimeList_v4.exe"
Write-Host "Note: copy the date folder next to the exe when running from a new directory."

exit 0
