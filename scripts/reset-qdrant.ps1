Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "Stopping Qdrant..."
docker compose stop qdrant

Write-Host "Removing Qdrant container..."
docker compose rm -f qdrant

$volumeName = "docmind_qdrant_data"
$volume = docker volume ls --format "{{.Name}}" | Where-Object { $_ -eq $volumeName }
if ($volume) {
    Write-Host "Removing vector index volume $volumeName..."
    docker volume rm $volumeName
} else {
    Write-Host "Qdrant volume $volumeName does not exist."
}

Write-Host "Starting Qdrant and dependent services..."
docker compose up -d qdrant backend frontend

Write-Host "Qdrant reset complete. Re-run document synchronization to rebuild vectors."
