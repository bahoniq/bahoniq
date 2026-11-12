$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$icon = Join-Path $root 'assets\bahoniq_italy.ico'
$source = Join-Path $root 'BahonIQ_Launcher.cs'
$output = Join-Path $root 'BahonIQ.exe'
$csc = @(
    "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $csc) { throw 'C# compiler csc.exe not found. Install .NET Framework 4.x.' }
if (-not (Test-Path -LiteralPath $icon)) { throw "Icon file not found: $icon" }
if (-not (Test-Path -LiteralPath $source)) { throw "Source file not found: $source" }
if (-not (Test-Path -LiteralPath (Join-Path $root 'launcher.pyw'))) { throw 'launcher.pyw not found in Work center folder.' }
& $csc /nologo /target:winexe /platform:anycpu /optimize+ /codepage:65001 "/win32icon:$icon" "/out:$output" /reference:System.Windows.Forms.dll "$source"
if ($LASTEXITCODE -ne 0) { throw "Compilation failed with exit code $LASTEXITCODE" }
Write-Host "Build complete: $output" -ForegroundColor Green
