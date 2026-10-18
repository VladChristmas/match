#Requires -Version 5.1
# Загружает окружение MSVC (vcvars64) в текущую PowerShell-сессию.
# Нужно для сборки Rust/Tauri, т.к. VS BuildTools 2022 не зарегистрирован в vswhere.
#
# Использование:
#   . .\scripts\dev-env.ps1      # dot-source, чтобы переменные попали в текущую сессию

$vcvarsCandidates = @(
    "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
    "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
)
$vcvarsCandidates += Get-ChildItem -Path "C:\Program Files*\Microsoft Visual Studio\*\*\VC\Auxiliary\Build\vcvars64.bat" -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty FullName

$vcvars = $vcvarsCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $vcvars) {
    Write-Error "vcvars64.bat не найден. Установите VS BuildTools с workload VCTools (см. .\scripts\msvc-status.ps1)."
    return
}

$envDump = cmd /c "`"$vcvars`" >nul 2>&1 && set"
foreach ($line in $envDump) {
    if ($line -match '^([^=]+)=(.*)$') {
        Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2]
    }
}

$cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
if (($env:Path -split ';') -notcontains $cargoBin) {
    $env:Path = "$cargoBin;$env:Path"
}

Write-Host "MSVC-окружение загружено. cl/link и cargo готовы." -ForegroundColor Green
