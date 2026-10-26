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

# Docker/NOTICE на stderr: PowerShell 5.1 при EAP=Stop оборачивает их в
# NativeCommandError и обрывает скрипт. Вызовы идут через cmd /c — stderr
# подавляется на уровне cmd, stdout возвращается как обычно.
function Invoke-Docker {
    param([Parameter(Mandatory = $true)][string]$CommandLine)
    return (& cmd /c "$CommandLine 2>NUL")
}

Invoke-Docker "docker exec $Container sh -c `"pg_dump -U $User -d $Database -Fc -f /tmp/match-backup.dump`""
Invoke-Docker "docker cp ${Container}`:/tmp/match-backup.dump `"$target`""
Invoke-Docker "docker exec $Container rm -f /tmp/match-backup.dump"

$size = (Get-Item $target).Length
if ($size -le 0) {
    throw "Backup is empty: $target"
}
Write-Output "OK $target ($size bytes)"
