<#
.SYNOPSIS
    Проверка восстановления резервной копии PostgreSQL для MATCH (runbook §11).
.DESCRIPTION
    Восстанавливает дамп (scripts/backup_pg.ps1) в отдельную БУ <TargetDatabase>,
    сверяет число таблиц с исходным и удаляет проверочную БУ.
    Использование: scripts\restore_pg.ps1 -BackupFile <путь>
                   [-Container infra-db-1] [-SourceDatabase match]
                   [-TargetDatabase match_restore_check] [-Keep]
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$Container = "infra-db-1",
    [string]$SourceDatabase = "match",
    [string]$TargetDatabase = "match_restore_check",
    [switch]$Keep
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupFile)) {
    throw "Backup file not found: $BackupFile"
}

# Docker/NOTICE на stderr: PowerShell 5.1 при EAP=Stop оборачивает их в
# NativeCommandError и обрывает скрипт (баг чистого прогона). Вызовы идут через
# cmd /c — stderr подавляется на уровне cmd, stdout возвращается как обычно.
function Invoke-Docker {
    param([Parameter(Mandatory = $true)][string]$CommandLine)
    return (& cmd /c "$CommandLine 2>NUL")
}

Invoke-Docker "docker cp `"$BackupFile`" ${Container}:/tmp/restore-check.dump"
Invoke-Docker "docker exec $Container sh -c `"dropdb --if-exists -U match $TargetDatabase`""
Invoke-Docker "docker exec $Container sh -c `"createdb -U match $TargetDatabase`""
Invoke-Docker "docker exec $Container sh -c `"pg_restore -U match -d $TargetDatabase --no-owner /tmp/restore-check.dump`""

$src = Invoke-Docker "docker exec $Container psql -U match -d $SourceDatabase -tAc `"select count(*) from information_schema.tables where table_schema='public';`""
$dst = Invoke-Docker "docker exec $Container psql -U match -d $TargetDatabase -tAc `"select count(*) from information_schema.tables where table_schema='public';`""

if ($src.Trim() -ne $dst.Trim()) {
    Invoke-Docker "docker exec $Container sh -c `"rm -f /tmp/restore-check.dump`""
    throw "Table count mismatch: source=$src restored=$dst"
}

$version = Invoke-Docker "docker exec $Container psql -U match -d $TargetDatabase -tAc `"select version_num from alembic_version;`""
Write-Output "OK restored tables=$dst alembic=$($version.Trim()) into $TargetDatabase"

if (-not $Keep) {
    Invoke-Docker "docker exec $Container sh -c `"dropdb --if-exists -U match $TargetDatabase && rm -f /tmp/restore-check.dump`""
}
