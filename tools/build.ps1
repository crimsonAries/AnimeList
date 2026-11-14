# One-click build for AnimeList_v4.4 (Windows / PowerShell)
# Usage: powershell -ExecutionPolicy Bypass -File .\tools\build.ps1
# Output: dist\AnimeList_v4.exe and root AnimeList_v4.exe

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    throw "Virtual environment .venv not found. Run: python -m venv .venv"
}

& $py -m pip install -r requirements/dev.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }

& $py -m PyInstaller --clean --noconfirm --onefile --noconsole `
    --name AnimeList_v4 `
    --icon bgm.ico `
    --add-data "index.html;." `
    main.py
if ($LASTEXITCODE -ne 0) { throw "Build failed" }

Copy-Item (Join-Path $root 'dist\AnimeList_v4.exe') (Join-Path $root 'AnimeList_v4.exe') -Force

Write-Host ""
Write-Host "Build complete: $root\dist\AnimeList_v4.exe"
Write-Host "Copied to: $root\AnimeList_v4.exe"
Write-Host "Note: copy the date folder next to the exe when running from a new directory."

exit 0
