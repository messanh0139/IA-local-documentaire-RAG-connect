Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Uvicorn = Join-Path $ProjectRoot ".venv\Scripts\uvicorn.exe"

Set-Location $ProjectRoot

if (-not (Test-Path $Python)) {
    Write-Error "Virtual environment not found. Run: python -m venv .venv"
    exit 1
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}

Write-Host "Checking Docker Desktop..."
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Docker Desktop is not running or the Docker engine is unavailable."
    Write-Host "Open Docker Desktop, wait until it says 'Engine running', then run again:"
    Write-Host "  .\scripts\start-dev.ps1"
    exit 1
}

Write-Host "Starting PostgreSQL, Qdrant and Redis..."
docker compose up -d postgres qdrant redis
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose up failed."
    exit 1
}

Write-Host "Waiting for PostgreSQL..."
$deadline = (Get-Date).AddSeconds(90)
do {
    docker compose exec -T postgres pg_isready -U docmind -d docmind *> $null
    if ($LASTEXITCODE -eq 0) {
        break
    }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

if ($LASTEXITCODE -ne 0) {
    Write-Error "PostgreSQL did not become ready after 90 seconds."
    exit 1
}

Write-Host "Initializing database tables..."
$env:PYTHONPATH = "backend"
& $Python -m app.db.init_db
if ($LASTEXITCODE -ne 0) {
    Write-Error "Database initialization failed."
    exit 1
}

Write-Host "Starting FastAPI on http://localhost:8000"
& $Uvicorn app.main:app --app-dir backend --reload
