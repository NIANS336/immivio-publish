param([ValidateSet('Start','Stop','Status')][string]$Action = 'Status')
$ErrorActionPreference = 'Stop'
$taskName = 'Immivio-AI-Captions'
if ($Action -eq 'Start') {
    if (-not (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)) {
        $python = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
        $config = Join-Path $PSScriptRoot 'config.private.json'
        $taskAction = New-ScheduledTaskAction -Execute $python -Argument "-m immivio_caption --config `"$config`"" -WorkingDirectory $PSScriptRoot
        $principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $taskName -Action $taskAction -Principal $principal -Settings $settings | Out-Null
    }
    Start-ScheduledTask -TaskName $taskName
} elseif ($Action -eq 'Stop') {
    Stop-ScheduledTask -TaskName $taskName
}
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State
if ($Action -ne 'Stop') {
    try { Invoke-RestMethod 'http://127.0.0.1:8773/health' -TimeoutSec 3 | ConvertTo-Json }
    catch { Write-Output 'Bridge HTTP is not ready yet.' }
}
