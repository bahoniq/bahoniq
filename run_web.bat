@echo off
setlocal
cd /d "%~dp0"
title BahonIQ Web Center Server
echo ========================================================
echo         BAHONIQ WORK CENTER - СЕТЕВОЙ ВЕБ-СЕРВЕР
echo ========================================================
echo.
echo [1] ДЛЯ ВАС (на этом компьютере):
echo     http://localhost:8000
echo     или http://127.0.0.1:8000
echo.
echo [2] ДЛЯ КОЛЛЕГ В СЕТИ (с других компьютеров):
echo     http://10.20.25.162:8000
echo.
echo ========================================================
echo Сервер запущен. Не закрывайте это окно!
echo ========================================================
echo.

"C:\Users\user\AppData\Local\Programs\Python\Python314\python.exe" -m uvicorn web_app.server:app --host 0.0.0.0 --port 8000
pause
