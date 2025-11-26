@echo off
REM LLM Council - Quick Launch
REM Starts backend and opens dashboard in browser

set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%.."
set "PYTHON_DIR=%APP_DIR%\python"
set "BACKEND_DIR=%APP_DIR%\backend"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "DATA_DIR=%APP_DIR%\data"

REM Create data directories if not exist
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%DATA_DIR%\conversations" mkdir "%DATA_DIR%\conversations"
if not exist "%DATA_DIR%\documents" mkdir "%DATA_DIR%\documents"

REM Check if backend is already running
curl -s http://localhost:8001/ >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo LLM Council is already running!
    start http://localhost:8001
    exit /b 0
)

REM Set environment
set "PYTHONPATH=%BACKEND_DIR%"
set "DATA_DIR=%DATA_DIR%"

echo Starting LLM Council...
echo.

REM Start backend server in background
cd /d "%BACKEND_DIR%"
start "LLM Council" /B /MIN "%PYTHON_EXE%" -m uvicorn main:app --host 127.0.0.1 --port 8001

REM Wait for server to start
echo Waiting for server to start...
set /a count=0
:waitloop
timeout /t 1 /nobreak >nul
curl -s http://localhost:8001/ >nul 2>&1
if %ERRORLEVEL% EQU 0 goto serverready
set /a count+=1
if %count% LSS 15 goto waitloop
echo Server failed to start in time.
pause
exit /b 1

:serverready
echo Server is ready!
echo.
echo Opening LLM Council in your browser...
start http://localhost:8001

echo.
echo LLM Council is running at: http://localhost:8001
echo.
echo To stop: Close this window or run stop_services.bat
echo.
