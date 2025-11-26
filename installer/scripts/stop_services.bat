@echo off
REM LLM Council - Stop Services
REM Stops all running LLM Council processes

echo Stopping LLM Council services...

REM Kill Python processes running uvicorn
taskkill /F /IM python.exe /FI "WINDOWTITLE eq LLM Council*" > nul 2>&1
taskkill /F /FI "WINDOWTITLE eq LLM Council Backend" > nul 2>&1

REM Kill any uvicorn processes on port 8001
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8001 ^| findstr LISTENING') do (
    taskkill /F /PID %%a > nul 2>&1
)

echo Services stopped.
