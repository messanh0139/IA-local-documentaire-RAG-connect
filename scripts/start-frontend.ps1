Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendRoot = Join-Path $ProjectRoot "frontend"

Set-Location $FrontendRoot

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "npm is not available on this machine."
    Write-Host "Install Node.js LTS, then run:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1"
    exit 1
}

if (-not (Test-Path ".env.local")) {
    Copy-Item ".env.local.example" ".env.local"
    Write-Host "Created frontend\.env.local from .env.local.example"
}

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..."
    npm install
}

Write-Host "Starting Next.js on http://localhost:3000"
npm run dev
