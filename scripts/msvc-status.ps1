#Requires -Version 5.1
# Диагностика MSVC-окружения для сборки Rust/Tauri (Этап 19, OQ-4).
#
# Решение по OQ-4: остаёмся на `scripts/dev-env.ps1` (dot-source), полная
# регистрация VS BuildTools в vswhere не требуется — она требует прав администратора
# и переустанавливает компоненты. Этот скрипт только сообщает состояние и рекомендацию.
#
# Запуск:
#   .\scripts\msvc-status.ps1

$ErrorActionPreference = "Continue"

$installer = "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
$buildToolsVcvars = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
$msvcRoot = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10\Include"

Write-Host "== MSVC status (OQ-4) ==" -ForegroundColor Cyan

$instances = @()
if (Test-Path -LiteralPath $installer) {
    $instances = @(& $installer -all -products * -format value -property installationPath 2>$null)
}
if ($instances.Count -gt 0) {
    Write-Host "[ok]   vswhere видит инсталляции:" -ForegroundColor Green
    $instances | ForEach-Object { Write-Host "         $_" }
} else {
    Write-Host "[warn] vswhere не видит ни одной инсталляции (ожидаемо для этого окружения)." -ForegroundColor Yellow
}

if (Test-Path -LiteralPath $buildToolsVcvars) {
    Write-Host "[ok]   vcvars64.bat найден: $buildToolsVcvars" -ForegroundColor Green
} else {
    Write-Host "[fail] vcvars64.bat НЕ найден. Установите VS BuildTools с workload VCTools." -ForegroundColor Red
}

$toolsets = if (Test-Path -LiteralPath $msvcRoot) { @(Get-ChildItem -LiteralPath $msvcRoot -Directory) } else { @() }
if ($toolsets.Count -gt 0) {
    Write-Host "[ok]   MSVC toolset: $($toolsets.Name -join ', ')" -ForegroundColor Green
} else {
    Write-Host "[warn] MSVC toolset не найден под $msvcRoot." -ForegroundColor Yellow
}

$sdks = if (Test-Path -LiteralPath $sdkRoot) { @(Get-ChildItem -LiteralPath $sdkRoot -Directory) } else { @() }
if ($sdks.Count -gt 0) {
    Write-Host "[ok]   Windows SDK: $($sdks.Name -join ', ')" -ForegroundColor Green
} else {
    Write-Host "[warn] Windows SDK не найден под $sdkRoot." -ForegroundColor Yellow
}

Write-Host ""
if ((Test-Path -LiteralPath $buildToolsVcvars) -and $toolsets.Count -gt 0 -and $sdks.Count -gt 0) {
    Write-Host "Итог: окружение готово. Перед сборкой выполняйте:" -ForegroundColor Green
    Write-Host "  . .\scripts\dev-env.ps1" -ForegroundColor Green
    Write-Host "Полная регистрация BuildTools в vswhere (требует прав администратора) не требуется — см. ADR-0025."
} else {
    Write-Host "Итог: окружения MSVC недостаточно. Установите VS BuildTools 2022 с workload" -ForegroundColor Yellow
    Write-Host "'Desktop development with C++' (VCTools + Windows SDK)."
}
