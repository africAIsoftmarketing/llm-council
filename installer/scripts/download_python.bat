@echo off
REM ==============================================
REM Download and setup embedded Python
REM ==============================================

set "SCRIPT_DIR=%~dp0"
set "PYTHON_DIR=%SCRIPT_DIR%..\embedded-python"
set "PYTHON_VERSION=3.11.9"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip"

echo.
echo ============================================
echo   Downloading Embedded Python %PYTHON_VERSION%
echo ============================================
echo.

REM Create directory
if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"
cd /d "%PYTHON_DIR%"

REM Check if already exists
if exist "python.exe" (
    echo Python already downloaded. Delete the folder to re-download.
    pause
    exit /b 0
)

echo Downloading Python embeddable package...
curl -L -o python-embed.zip "%PYTHON_URL%"

if not exist "python-embed.zip" (
    echo ERROR: Download failed!
    pause
    exit /b 1
)

echo Extracting...
tar -xf python-embed.zip
del python-embed.zip

echo.
echo Downloading pip installer...
curl -L -o get-pip.py "https://bootstrap.pypa.io/get-pip.py"

echo Installing pip...
python.exe get-pip.py
del get-pip.py

echo.
echo Enabling site-packages (editing python311._pth)...
powershell -Command "(Get-Content python311._pth) -replace '#import site', 'import site' | Set-Content python311._pth"

echo.
echo Installing required packages...
python.exe -m pip install --upgrade pip
python.exe -m pip install fastapi uvicorn python-dotenv httpx pydantic PyPDF2 python-docx python-pptx Pillow python-multipart aiofiles

echo.
echo ============================================
echo   Embedded Python Setup Complete!
echo ============================================
echo.
echo Location: %PYTHON_DIR%
echo.

pause
