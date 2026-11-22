# 安装到当前用户（无需管理员权限）
# 用法：powershell -ExecutionPolicy Bypass -File .\install.ps1
# 可选：-NoStart 安装后不自动启动

param(
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
$sourceDir = $PSScriptRoot
$installDir = Join-Path $env:LOCALAPPDATA "Programs\RiJin"
$appPy = Join-Path $installDir "app.py"
$dataDir = Join-Path $env:APPDATA "RiJin"
$shortcutName = "日进.lnk"

Write-Host ""
Write-Host "  日进 · 每日任务进度管理" -ForegroundColor DarkGreen
Write-Host "  ------------------------------" -ForegroundColor DarkGray
Write-Host ""

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    throw "未找到 Python。请先安装 Python 3.9+，并确保 python 命令可用。"
}
$python = $pythonCommand.Source
$pythonDir = Split-Path -Parent $python
$pythonw = Join-Path $pythonDir "pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonw)) {
    $pythonw = $python
}

Write-Host "检查运行环境..." -ForegroundColor DarkGray
& $python -c "import sys; import PyQt5.QtCore; print('Python', sys.version.split()[0], '| Qt', PyQt5.QtCore.QT_VERSION_STR)"
if ($LASTEXITCODE -ne 0) {
    throw "缺少 PyQt5。请先运行：python -m pip install PyQt5"
}

# 停掉正在运行的日进（源码版或已安装版），避免单实例把新版本挡在门外。
$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @("python.exe", "pythonw.exe") -and
    $_.CommandLine -and
    $_.CommandLine -like "*app.py*" -and
    ($_.CommandLine -like "*RiJin*" -or $_.CommandLine -like "*rijin*")
}
foreach ($proc in $running) {
    try {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "已停止运行中的实例：$($proc.ProcessId)" -ForegroundColor DarkGray
    } catch {
        # 忽略无法停止的进程，稍后启动时会由单实例机制处理
    }
}

if (Test-Path -LiteralPath $installDir) {
    $resolved = (Resolve-Path -LiteralPath $installDir).Path
    if ($resolved -notlike "*\Programs\RiJin") {
        throw "安装目录校验失败：$resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
New-Item -ItemType Directory -Path $installDir | Out-Null

Write-Host "复制程序文件..." -ForegroundColor DarkGray
Copy-Item -LiteralPath (Join-Path $sourceDir "app.py") -Destination $installDir
Copy-Item -LiteralPath (Join-Path $sourceDir "README.md") -Destination $installDir
Copy-Item -LiteralPath (Join-Path $sourceDir "requirements.txt") -Destination $installDir
Copy-Item -LiteralPath (Join-Path $sourceDir "rijin") -Destination $installDir -Recurse
Copy-Item -LiteralPath (Join-Path $sourceDir "assets") -Destination $installDir -Recurse
if (Test-Path -LiteralPath (Join-Path $sourceDir "docs")) {
    Copy-Item -LiteralPath (Join-Path $sourceDir "docs") -Destination $installDir -Recurse
}
Get-ChildItem -LiteralPath $installDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$shell = New-Object -ComObject WScript.Shell
function New-RiJinShortcut {
    param([string]$Path)
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = '"' + $appPy + '"'
    $shortcut.WorkingDirectory = $installDir
    $shortcut.IconLocation = (Join-Path $installDir "assets\icon.ico") + ",0"
    $shortcut.Description = "日进 · 每日任务进度管理"
    $shortcut.WindowStyle = 1
    $shortcut.Save()
}

$desktop = [Environment]::GetFolderPath("Desktop")
$programs = [Environment]::GetFolderPath("Programs")
New-RiJinShortcut (Join-Path $desktop $shortcutName)
New-RiJinShortcut (Join-Path $programs $shortcutName)

Write-Host "配置开机自启..." -ForegroundColor DarkGray
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
New-Item -Path $runKey -Force | Out-Null
$runCommand = '"' + $pythonw + '" "' + $appPy + '"'
Set-ItemProperty -Path $runKey -Name "RiJin" -Value $runCommand -Type String

New-Item -ItemType Directory -Path $dataDir -Force | Out-Null

Write-Host ""
Write-Host "安装完成" -ForegroundColor Green
Write-Host "  程序：$installDir"
Write-Host "  数据：$dataDir"
Write-Host "  快捷方式：桌面 / 开始菜单「日进」"
Write-Host ""

if (-not $NoStart) {
    Start-Process -FilePath $pythonw -ArgumentList ('"' + $appPy + '"') -WorkingDirectory $installDir
    Write-Host "已启动日进，稍候可在桌面右上角看到悬浮窗。" -ForegroundColor Green
} else {
    Write-Host "已跳过自动启动（-NoStart）。" -ForegroundColor DarkGray
}
Write-Host ""
