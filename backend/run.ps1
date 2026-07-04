# Run the takt-bots backend (FastAPI on port 8020).
# Run from the repo root so `database`, `agents`, `tools`, `shared_env` are importable.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtualenv..."
    python -m venv (Join-Path $repoRoot "backend\.venv")
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r (Join-Path $repoRoot "backend\requirements.txt")
}

& $venvPython -m uvicorn backend.app.main:app --port 8020 --reload
