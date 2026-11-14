$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$py = Join-Path $here '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    throw 'Virtual environment .venv not found. Run: python -m venv .venv'
}

& $py (Join-Path $here 'package_release.py')
if ($LASTEXITCODE -ne 0) { throw 'Release packaging failed' }
exit 0
