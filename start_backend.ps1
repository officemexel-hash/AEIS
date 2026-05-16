$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ScriptDir "src\sylion-pipeline"

Set-Location $BackendDir
$env:PYTHONUNBUFFERED = "1"

python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010
