@echo off
chcp 65001 >nul
setlocal
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
title BahonIQ Web Center Server

if not exist "%~dp0run_web.py" goto missing_script
if not exist "%~dp0web_app\server.py" goto missing_project

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
    goto launch
)
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    goto launch
)
where py >nul 2>&1
if errorlevel 1 goto find_python
py -3.14 -c "import sys" >nul 2>&1
if errorlevel 1 goto find_python
set "PYTHON_EXE=py"
set "PYTHON_ARGS=-3.14"
goto launch

:find_python
where python >nul 2>&1
if errorlevel 1 goto missing_python
set "PYTHON_EXE=python"

:launch
"%PYTHON_EXE%" %PYTHON_ARGS% -X utf8 "%~dp0run_web.py"
set "SERVER_EXIT=%ERRORLEVEL%"
if "%SERVER_EXIT%"=="0" exit /b 0
echo.
echo Server stopped with an error. See the message above.
pause
exit /b %SERVER_EXIT%

:missing_script
echo ERROR: run_web.py must be next to this BAT file.
pause
exit /b 1

:missing_project
echo ERROR: Put both launchers in the Work Center project folder.
echo Expected file: web_app\server.py
pause
exit /b 1

:missing_python
echo ERROR: Python was not found. Install Python or activate the project environment.
pause
exit /b 1
