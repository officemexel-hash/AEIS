# SYLION Worker Runtime -- Windows Service Installer (Scheduled Task)
# Creates a persistent background task that runs the worker runtime loop.
#
# Usage (Admin PowerShell):
#   .\scripts\install_worker_service.ps1 -WorkerName "Worker-A" -Capacity 3 -Tags "core"
#
# To remove:
#   Unregister-ScheduledTask -TaskName "SYLION_Worker_*" -Confirm:$false

param(
    [string]$WorkerName = "SYLION-Worker",
    [string]$HostName = "localhost",
    [int]$Capacity = 3,
    [string]$Tags = "core",
    [int]$Interval = 60,
    [string]$PythonPath = "",
    [string]$WorkingDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $WorkingDir) {
    $WorkingDir = (Get-Location).Path
}
if (-not $PythonPath) {
    $PythonPath = Join-Path $WorkingDir ".venv\Scripts\python.exe"
}

$ScriptPath = Join-Path $WorkingDir "scripts\run_worker.py"
$TaskName = "SYLION_Worker_$WorkerName"

if (-not (Test-Path $PythonPath)) {
    Write-Host "[ERROR] Python not found at $PythonPath" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $ScriptPath)) {
    Write-Host "[ERROR] Script not found at $ScriptPath" -ForegroundColor Red
    exit 1
}

$ActionArgs = "`"$ScriptPath`" --register `"$WorkerName`" --host `"$HostName`" --capacity $Capacity --tags `"$Tags`" --loop --interval $Interval"

$Action = New-ScheduledTaskAction -Execute "`"$PythonPath`"" -Argument $ActionArgs -WorkingDirectory $WorkingDir

# Run at startup, restart every 5 minutes on failure
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 5)

# Run as SYSTEM with highest privileges
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null

Write-Host ""
Write-Host "[OK] SYLION Worker service installed: $TaskName" -ForegroundColor Green
Write-Host "     Worker: $WorkerName | Capacity: $Capacity | Interval: ${Interval}s" -ForegroundColor Cyan
Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  Start:   Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  Stop:    Stop-ScheduledTask  -TaskName '$TaskName'"
Write-Host "  Status:  Get-ScheduledTask    -TaskName '$TaskName'"
Write-Host "  Remove:  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
Write-Host ""
