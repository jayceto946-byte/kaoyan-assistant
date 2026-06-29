param(
    [string]$OutputDir = "backups"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$dataRoot = Join-Path $root "data"
if (-not (Test-Path $dataRoot)) {
    throw "data directory not found: $dataRoot"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $root $OutputDir
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

$archivePath = Join-Path $backupDir "learning_data_$timestamp.zip"
$items = @(
    "data\progress",
    "data\images",
    "data\books",
    "data\chapters"
)

$existing = foreach ($item in $items) {
    $path = Join-Path $root $item
    if (Test-Path $path) { $path }
}

if (-not $existing -or $existing.Count -eq 0) {
    throw "No learning data directories found to back up."
}

Compress-Archive -Path $existing -DestinationPath $archivePath -Force
Write-Host "Backup created: $archivePath"
