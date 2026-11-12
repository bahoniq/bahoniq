@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_BahonIQ.ps1"
if errorlevel 1 (
  echo.
  echo Build failed. Read the error above.
)
pause
