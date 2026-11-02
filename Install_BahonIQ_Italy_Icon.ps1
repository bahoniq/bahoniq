$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $ProjectRoot "launcher.pyw"
$Icon = Join-Path $ProjectRoot "assets\bahoniq_italy.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "BahonIQ - Work Center.lnk"

if (-not (Test-Path -LiteralPath $Launcher)) {
    throw "Не найден launcher.pyw: $Launcher"
}

if (-not (Test-Path -LiteralPath $Icon)) {
    throw "Не найдена иконка: $Icon"
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.IconLocation = "$Icon,0"
$Shortcut.Description = "BahonIQ Work Center"
$Shortcut.Save()

$ShellApp = New-Object -ComObject Shell.Application
$ShellApp.NameSpace(0).Self.InvokeVerb("Refresh")

Write-Host "BahonIQ icon installed: $ShortcutPath" -ForegroundColor Green
