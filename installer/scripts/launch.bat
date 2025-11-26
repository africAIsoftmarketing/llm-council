@echo off
REM LLM Council - Quick Launch
REM Starts backend and opens dashboard in browser

set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%.."
set "PYTHON_DIR=%APP_DIR%\python"
set "BACKEND_DIR=%APP_DIR%\backend"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"

REM Data will be stored in AppData (handled by Python)
REM %APPDATA%\LLM Council\data\

REM Check if backend is already running
curl -s http://localhost:8001/api/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo LLM Council is already running!
    start http://localhost:8001
    exit /b 0
)

REM Set environment
set "PYTHONPATH=%BACKEND_DIR%"

echo ============================================
echo   LLM Council - Starting Server
echo ============================================
echo.
echo Data location: %APPDATA%\LLM Council\data
echo.

REM Start backend server in background
cd /d "%BACKEND_DIR%"
start "LLM Council Server" /MIN "%PYTHON_EXE%" -m uvicorn main:app --host 127.0.0.1 --port 8001

REM Wait for server to start
echo Waiting for server to start...
set /a count=0
:waitloop
timeout /t 1 /nobreak >nul
curl -s http://localhost:8001/ >nul 2>&1
if %ERRORLEVEL% EQU 0 goto serverready
set /a count+=1
if %count% LSS 15 goto waitloop
echo.
echo ERROR: Server failed to start in time.
echo Check if port 8001 is already in use.
pause
exit /b 1

:serverready
echo Server is ready!
echo.
echo Opening LLM Council in your browser...
start http://localhost:8001

echo.
echo ============================================
echo   LLM Council is running!
echo ============================================
echo.
echo Web Dashboard: http://localhost:8001
echo.
echo To stop: Close this window or press any key
echo.
pause >nul
REM Stop server when user presses a key
taskkill /FI "WINDOWTITLE eq LLM Council Server*" >nul 2>&1
echo Server stopped.
