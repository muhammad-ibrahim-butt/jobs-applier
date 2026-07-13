# Register a Windows Task Scheduler job for jobs-applier
# Run this script as Administrator

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$TaskName = "JobsApplier"
$IntervalMinutes = 120

# Find uv executable
$UvPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $UvPath) {
    Write-Error "uv not found in PATH. Install uv first: https://docs.astral.sh/uv/"
}

$Action = New-ScheduledTaskAction `
    -Execute $UvPath `
    -Argument "run jobs-applier run" `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Force

Write-Host "Task '$TaskName' registered successfully."
Write-Host "Runs every $IntervalMinutes minutes in: $ProjectRoot"
Write-Host ""
Write-Host "To run manually:  schtasks /Run /TN $TaskName"
Write-Host "To remove:        Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
