@echo off
REM LLM Council - Start Services
REM Starts the backend server and opens the web UI

set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%.."
set "PYTHON_DIR=%APP_DIR%\python"
set "BACKEND_DIR=%APP_DIR%\backend"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "DATA_DIR=%APP_DIR%\data"

REM Create data directory if not exists
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%DATA_DIR%\conversations" mkdir "%DATA_DIR%\conversations"
if not exist "%DATA_DIR%\documents" mkdir "%DATA_DIR%\documents"

REM Set environment variables
set "DATA_DIR=%DATA_DIR%"
set "PYTHONPATH=%BACKEND_DIR%"

echo Starting LLM Council Backend Server...
echo.

REM Start backend server
cd /d "%BACKEND_DIR%"
start "LLM Council Backend" /B "%PYTHON_EXE%" -m uvicorn main:app --host 0.0.0.0 --port 8001

REM Wait for server to start
echo Waiting for server to start...
timeout /t 3 /nobreak > nul

REM Open browser
echo Opening LLM Council in your browser...
start http://localhost:3000

echo.
echo LLM Council is running!
echo Backend: http://localhost:8001
echo Frontend: http://localhost:3000
echo.
echo Press any key to stop the server...
pause > nul

REM Stop server
taskkill /F /FI "WINDOWTITLE eq LLM Council Backend" > nul 2>&1
echo Server stopped.
