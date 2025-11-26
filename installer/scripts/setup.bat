@echo off
REM LLM Council Setup Script
REM Installs Python dependencies using embedded Python

echo ============================================
echo LLM Council - Installing Dependencies
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%.."
set "PYTHON_DIR=%APP_DIR%\python"
set "BACKEND_DIR=%APP_DIR%\backend"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "PIP_EXE=%PYTHON_DIR%\Scripts\pip.exe"

REM Check if Python exists
if not exist "%PYTHON_EXE%" (
    echo ERROR: Embedded Python not found at %PYTHON_EXE%
    echo Please reinstall LLM Council.
    pause
    exit /b 1
)

echo Found Python at: %PYTHON_EXE%
echo.

REM Upgrade pip
echo [1/3] Upgrading pip...
"%PYTHON_EXE%" -m pip install --upgrade pip --quiet

REM Install required packages
echo [2/3] Installing Python packages...
"%PYTHON_EXE%" -m pip install fastapi uvicorn python-dotenv httpx pydantic PyPDF2 python-docx python-pptx Pillow python-multipart aiofiles --quiet

REM Verify installation
echo [3/3] Verifying installation...
"%PYTHON_EXE%" -c "import fastapi; import uvicorn; print('All packages installed successfully!')"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install some packages.
    echo Please check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo ============================================
echo Installation Complete!
echo ============================================
echo.

exit /b 0
