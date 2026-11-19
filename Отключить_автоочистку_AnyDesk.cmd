@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Отключение автоочистки AnyDesk
echo Отключение автоочистки AnyDesk...
echo.
py scripts/schedule_anydesk_clean.py uninstall
echo.
echo ======================================================
echo Расписание автоочистки AnyDesk отключено.
echo ======================================================
echo.
pause
