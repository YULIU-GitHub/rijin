# 卸载日进（保留任务数据）
# 用法：powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
# 可选：-PurgeData 同时删除任务数据与日志

param(
    [switch]$PurgeData
)

$ErrorActionPreference = "Stop"
$installDir = Join-Path $env:LOCALAPPDATA "Programs\RiJin"
$dataDir = Join-Path $env:APPDATA "RiJin"
$shortcutName = "日进.lnk"

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @("python.exe", "pythonw.exe") -and
    $_.CommandLine -and
    $_.CommandLine -like "*$installDir*app.py*"
}
foreach ($proc in $running) {
    try {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    } catch {
    }
}

$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Remove-ItemProperty -Path $runKey -Name "RiJin" -ErrorAction SilentlyContinue

$desktop = [Environment]::GetFolderPath("Desktop")
$programs = [Environment]::GetFolderPath("Programs")
Remove-Item -LiteralPath (Join-Path $desktop $shortcutName) -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $programs $shortcutName) -Force -ErrorAction SilentlyContinue

if (Test-Path -LiteralPath $installDir) {
    $resolved = (Resolve-Path -LiteralPath $installDir).Path
    if ($resolved -like "*\Programs\RiJin") {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

if ($PurgeData -and (Test-Path -LiteralPath $dataDir)) {
    $resolvedData = (Resolve-Path -LiteralPath $dataDir).Path
    if ($resolvedData -like "*\AppData\Roaming\RiJin") {
        Remove-Item -LiteralPath $resolvedData -Recurse -Force
        Write-Host "已删除任务数据：$resolvedData" -ForegroundColor Yellow
    }
} else {
    Write-Host "任务数据已保留：$dataDir" -ForegroundColor DarkGray
}

Write-Host "日进已卸载。" -ForegroundColor Green
