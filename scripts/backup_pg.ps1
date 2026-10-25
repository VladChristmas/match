<#
.SYNOPSIS
    Резервная копия PostgreSQL для MATCH (runbook §11).
.DESCRIPTION
    pg_dump формата custom (сжатый, поддерживает восстановление выборочно).
    Использование: scripts\backup_pg.ps1 [-Container infra-db-1] [-Database match]
                   [-User match] [-OutDir D:\Backup]
#>
param(
    [string]$Container = "infra-db-1",
    [string]$Database = "match",
    [string]$User = "match",
    [string]$OutDir = "D:\Backup"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path $OutDir "match-pg-$timestamp.dump"

docker exec $Container sh -c "pg_dump -U $User -d $Database -Fc -f /tmp/match-backup.dump"
docker cp "$Container`:/tmp/match-backup.dump" "$target"
docker exec $Container rm -f /tmp/match-backup.dump

$size = (Get-Item $target).Length
if ($size -le 0) {
    throw "Backup is empty: $target"
}
Write-Output "OK $target ($size bytes)"
