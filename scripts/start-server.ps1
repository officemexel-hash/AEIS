# Start SYLION Pipeline v6.2.0 dev server (PowerShell)
$ErrorActionPreference = "Stop"
$InstallDir = (Get-Location).Path
$SrcDir = Join-Path $InstallDir "src\sylion-pipeline"
$VenvDir = Join-Path $InstallDir ".venv"
$EnvFile = Join-Path $InstallDir ".env.generated"

if (-not (Test-Path (Join-Path $VenvDir "Scripts\Activate.ps1"))) {
    Write-Host "[ERROR] venv nie istnieje. Uruchom najpierw: .\scripts\install.ps1" -ForegroundColor Red
    exit 1
}
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | Where-Object { $_ -notmatch "^\s*#" -and $_ -match "=" } | ForEach-Object {
        $k, $v = $_ -split "=", 2
        [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), "Process")
    }
} else {
    Write-Host "[INFO] .env.generated nie istnieje. Startuję w czystym trybie local-first bez kluczy API." -ForegroundColor Yellow
}

$env:SYLION_USE_LEGACY_DB_PATH = "0"
$env:SESSION_COOKIE_SECURE = "0"
$env:SYLION_ENV = "dev"
$env:SYLION_AEIS_ENV = "dev"
$env:SYLION_RBAC_DISABLED = "1"
$env:SYLION_RATE_LIMIT_DISABLED = "1"
$env:SYLION_AUTH_BYPASS = "1"
$env:PYTHONPATH = "$SrcDir"
$env:LITELLM_LOCAL_MODEL_COST_MAP = "True"
$env:LITELLM_DO_NOT_TRACK = "True"

& (Join-Path $VenvDir "Scripts\Activate.ps1")
Set-Location $SrcDir

Write-Host ""
Write-Host "Serwer SYLION AEIS API startuje na http://127.0.0.1:8010" -ForegroundColor Cyan
Write-Host "Zatrzymanie: Ctrl+C (graceful shutdown do 10s)" -ForegroundColor Yellow
Write-Host ""

python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010 --timeout-graceful-shutdown 10
