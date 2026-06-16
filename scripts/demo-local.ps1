param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000/api/v1",
    [string]$RootPath = "/data/local-docs",
    [string]$Question = "Que dit la base documentaire sur les permissions et les sources ?"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Headers = @{
    "Content-Type" = "application/json"
    "X-Tenant-Id" = "deep-bleue-ia"
    "X-User-Id" = "alice"
    "X-User-Email" = "alice@deepbleue.ai"
    "X-User-Groups" = "everyone,finance,direction"
}

Write-Host "Checking backend..."
$ready = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/health/ready" -Headers $Headers
Write-Host "Backend readiness: $($ready.status)"

Write-Host "Creating local connector for $RootPath..."
$connectorBody = @{
    name = "Demo dossier local"
    type = "local"
    config = @{
        root_path = $RootPath
    }
} | ConvertTo-Json -Depth 5

$connector = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/connectors" -Headers $Headers -Body $connectorBody
Write-Host "Connector: $($connector.id)"

Write-Host "Synchronizing documents..."
$syncBody = @{ mode = "foreground" } | ConvertTo-Json
$sync = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/connectors/$($connector.id)/sync" -Headers $Headers -Body $syncBody
Write-Host "Sync status: $($sync.status), indexed: $($sync.files_indexed), seen: $($sync.files_seen)"

Write-Host "Asking RAG question..."
$chatBody = @{
    question = $Question
    top_k = 5
} | ConvertTo-Json
$chat = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/chat" -Headers $Headers -Body $chatBody

Write-Host ""
Write-Host "Answer:"
Write-Host $chat.answer
Write-Host ""
Write-Host "Sources:"
$chat.citations | ForEach-Object {
    Write-Host "- [$($_.source_id)] $($_.title) | $($_.path)"
}
