Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "Docker services:"
docker compose ps

Write-Host ""
Write-Host "FastAPI port 8000:"
$tcp = Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -WarningAction SilentlyContinue
if ($tcp.TcpTestSucceeded) {
    Write-Host "OK - FastAPI is listening on http://127.0.0.1:8000"
    try {
        $health = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing
        Write-Host "Health response:"
        Write-Host $health.Content
    } catch {
        Write-Host "Port is open, but /health did not respond correctly:"
        Write-Host $_.Exception.Message
    }
} else {
    Write-Host "KO - Nothing is listening on port 8000."
    Write-Host "Start the API with:"
    Write-Host "  .\scripts\start-dev.ps1"
    Write-Host ""
    Write-Host "Keep that terminal open while using http://127.0.0.1:8000/docs"
}
