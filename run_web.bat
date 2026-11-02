@echo off
setlocal
cd /d "%~dp0"
echo BahonIQ Work Center - local network
echo.
echo This computer: http://127.0.0.1:8000
echo Other computers: http://YOUR-IP:8000
echo.
py -m uvicorn web_app.server:app --host 0.0.0.0 --port 8000
pause
