$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'web/index.html'))) {
    throw 'Frontend build is missing. In frontend/, run pnpm install --frozen-lockfile and pnpm build first. See docs/FRONTEND.md.'
}
$pythonExe = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonCommand) { & py -3 -m venv .venv } else { & python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ is required. Install Python and try again.' }
}
& $pythonExe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Open http://127.0.0.1:8765 in your browser. Press Ctrl+C to stop.'
& $pythonExe server.py
