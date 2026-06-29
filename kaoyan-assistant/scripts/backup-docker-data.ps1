param(
    [string]$DataDir = "data",
    [string]$BackupDir = "backups"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$dataPath = Join-Path $root $DataDir

if (-not (Test-Path $dataPath)) {
    throw "Data directory not found: $dataPath"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = Join-Path $root $BackupDir
New-Item -ItemType Directory -Force -Path $backupPath | Out-Null

$archivePath = Join-Path $backupPath "docker_data_$timestamp.zip"
Compress-Archive -Path $dataPath -DestinationPath $archivePath -Force

Write-Host "Backup created: $archivePath"
