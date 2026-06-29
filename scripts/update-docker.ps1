param(
    [switch]$NoBackup,
    [switch]$Pull
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

if (-not (Test-Path ".env")) {
    throw ".env not found. Copy .env.example to .env and fill your API keys first."
}

New-Item -ItemType Directory -Force -Path ".\data" | Out-Null

if (-not $NoBackup -and (Test-Path ".\data")) {
    & ".\scripts\backup-docker-data.ps1"
}

if ($Pull) {
    docker compose pull
} else {
    docker compose build
}

docker compose down
docker compose up -d

Write-Host "Waiting for /health ..."
Start-Sleep -Seconds 5

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 10
    Write-Host "Health: $($health.status)"
    Write-Host "Open: http://127.0.0.1:8000"
} catch {
    Write-Warning "Container started, but health check failed. Check logs with: docker compose logs -f"
    throw
}
