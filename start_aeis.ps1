$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$BackendDir = Join-Path $ScriptDir "src\sylion-pipeline"
$FrontendDir = Join-Path $ScriptDir "src\sylion-frontend"

Start-Process -FilePath "powershell.exe" -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-File",
  (Join-Path $ScriptDir "start_backend.ps1")
) -WorkingDirectory $BackendDir

Start-Sleep -Seconds 5

Start-Process -FilePath "powershell.exe" -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-File",
  (Join-Path $ScriptDir "start_frontend.ps1")
) -WorkingDirectory $FrontendDir

Start-Sleep -Seconds 5
Start-Process "http://127.0.0.1:3001/overview"
