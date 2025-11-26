@echo off
REM ==============================================
REM LLM Council - Complete Build Script
REM Run this on Windows to build the installer
REM ==============================================

echo.
echo ============================================
echo   LLM Council Installer Build Script
echo ============================================
echo.

set "ROOT_DIR=%~dp0..\.."
set "INSTALLER_DIR=%~dp0.."
set "FRONTEND_DIR=%ROOT_DIR%frontend"
set "PYTHON_DIR=%INSTALLER_DIR%embedded-python"
set "OUTPUT_DIR=%INSTALLER_DIR%output"

REM Check for required tools
where node >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Node.js not found. Please install from https://nodejs.org/
    pause
    exit /b 1
)

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found. Please install from https://www.python.org/
    pause
    exit /b 1
)

echo [1/5] Building Frontend...
echo ----------------------------------------
cd /d "%FRONTEND_DIR%"
call npm install
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Frontend build failed!
    pause
    exit /b 1
)
echo Frontend build complete!
echo.

echo [2/5] Downloading Embedded Python...
echo ----------------------------------------
if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"
cd /d "%PYTHON_DIR%"

if not exist "python.exe" (
    echo Downloading Python 3.11 embeddable...
    curl -L -o python-embed.zip "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
    tar -xf python-embed.zip
    del python-embed.zip
    
    echo Installing pip...
    curl -L -o get-pip.py "https://bootstrap.pypa.io/get-pip.py"
    python.exe get-pip.py
    del get-pip.py
    
    echo Enabling site-packages...
    powershell -Command "(Get-Content python311._pth) -replace '#import site', 'import site' | Set-Content python311._pth"
) else (
    echo Embedded Python already exists, skipping download.
)
echo.

echo [3/5] Installing Python Packages...
echo ----------------------------------------
cd /d "%PYTHON_DIR%"
python.exe -m pip install --upgrade pip
python.exe -m pip install fastapi uvicorn python-dotenv httpx pydantic PyPDF2 python-docx python-pptx Pillow python-multipart aiofiles
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install Python packages!
    pause
    exit /b 1
)
echo Python packages installed!
echo.

echo [4/5] Creating Assets Directory...
echo ----------------------------------------
if not exist "%INSTALLER_DIR%assets" mkdir "%INSTALLER_DIR%assets"
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM Create a simple icon if not exists (placeholder)
if not exist "%INSTALLER_DIR%assets\icon.ico" (
    echo WARNING: No icon.ico found. Please add an icon file to installer\assets\icon.ico
)
echo.

echo [5/5] Building Installer with Inno Setup...
echo ----------------------------------------
set "INNO_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if exist "%INNO_PATH%" (
    "%INNO_PATH%" "%INSTALLER_DIR%inno-setup\llm-council-installer.iss"
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo ============================================
        echo   BUILD COMPLETE!
        echo ============================================
        echo.
        echo Installer created at:
        echo %OUTPUT_DIR%\LLMCouncil-Setup-2.0.0.exe
        echo.
    ) else (
        echo ERROR: Inno Setup compilation failed!
    )
) else (
    echo WARNING: Inno Setup not found at %INNO_PATH%
    echo Please install Inno Setup 6 from: https://jrsoftware.org/isdl.php
    echo Then run the build manually.
)

echo.
pause
