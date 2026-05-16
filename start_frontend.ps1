$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $ScriptDir "src\sylion-frontend"

Set-Location $FrontendDir
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:8010"

npm run dev -- --hostname 127.0.0.1 --port 3001
