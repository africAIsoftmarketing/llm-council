@echo off
REM LLM Council - Quick Launch
REM Opens the configuration dashboard in your default browser

set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%.."

REM Check if backend is running
curl -s http://localhost:8001/ > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Backend not running. Starting services...
    call "%APP_DIR%\scripts\start_services.bat"
) else (
    echo Opening LLM Council...
    start http://localhost:3000
)
