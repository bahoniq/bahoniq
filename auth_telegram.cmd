@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Авторизация Telegram - BahonIQ Music
py scripts/auth_telegram_music.py
echo.
pause
