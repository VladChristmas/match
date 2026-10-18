#Requires -Version 5.1
# Единая локальная проверка качества MATCH (Этап 13).
# Соответствует .github/workflows/ci.yml.
#
# Запуск:
#   . .\scripts\dev-env.ps1        # один раз в сессии: MSVC для Rust/Tauri
#   .\scripts\check.ps1

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot

$api = Join-Path $root "services\api"
$python = Join-Path $api ".venv\Scripts\python.exe"
$desktop = Join-Path $root "apps\desktop"
$manifest = Join-Path $desktop "src-tauri\Cargo.toml"

$failed = @()

function Invoke-Step {
    param([string]$Name, [string]$WorkDir, [scriptblock]$Command)

    Write-Host "==> $Name" -ForegroundColor Cyan
    Push-Location $WorkDir
    try {
        & $Command
        if (-not $?) { throw "step failed" }
    }
    catch {
        $script:failed += $Name
        Write-Host "!! $Name — FAILED" -ForegroundColor Red
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "Не найден venv: $python (создайте через python -m venv .venv)"
    exit 1
}

Invoke-Step "backend: ruff format --check" $api { & $python -m ruff format --check . }
Invoke-Step "backend: ruff check" $api { & $python -m ruff check . }
Invoke-Step "backend: pytest" $api { & $python -m pytest -q }
Invoke-Step "desktop: pnpm build" $desktop { & pnpm build }
Invoke-Step "desktop: cargo fmt --check" $desktop { & cargo fmt --manifest-path $manifest --check }
Invoke-Step "desktop: cargo clippy -D warnings" $desktop {
    & cargo clippy --manifest-path $manifest --all-targets -- -D warnings
}
Invoke-Step "desktop: cargo test" $desktop { & cargo test --manifest-path $manifest }

if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host "Провалено: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Все проверки пройдены." -ForegroundColor Green
