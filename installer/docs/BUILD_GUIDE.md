# LLM Council Windows Installer - Build Guide

This guide explains how to build the Windows installer for LLM Council from source.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Directory Structure](#directory-structure)
3. [Step-by-Step Build Process](#step-by-step-build-process)
4. [Building with Inno Setup](#building-with-inno-setup)
5. [Testing the Installer](#testing-the-installer)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

1. **Windows 10/11 (64-bit)** - Build machine
2. **Node.js 18+** - [Download](https://nodejs.org/)
3. **Python 3.11+** - [Download](https://www.python.org/downloads/)
4. **Inno Setup 6.x** - [Download](https://jrsoftware.org/isdl.php)
5. **Git** - [Download](https://git-scm.com/download/win)

### Optional (for Electron build)

6. **Visual Studio Build Tools** - For native module compilation
7. **7-Zip** - For archive extraction

---

## Directory Structure

```
llm-council/
├── backend/                    # Python backend source
├── frontend/                   # React frontend source
└── installer/
    ├── electron-app/          # Electron desktop wrapper
    │   ├── package.json
    │   ├── main.js
    │   ├── preload.js
    │   ├── splash.html
    │   └── dist/               # Built Electron app
    ├── inno-setup/
    │   └── llm-council-installer.iss
    ├── scripts/
    │   ├── setup.bat           # Post-install dependency setup
    │   ├── start_services.bat  # Service launcher
    │   ├── stop_services.bat   # Service stopper
    │   ├── launch.bat          # Quick launcher
    │   └── launcher.py         # Python/Tkinter GUI
    ├── embedded-python/       # Python embeddable package
    ├── config/
    │   └── default_config.json
    ├── assets/
    │   └── icon.ico
    ├── docs/
    │   └── README_INSTALLER.txt
    └── output/                 # Final installer output
```

---

## Step-by-Step Build Process

### Step 1: Clone the Repository

```powershell
git clone https://github.com/YOUR_REPO/llm-council.git
cd llm-council
```

### Step 2: Download Python Embeddable Package

Download Python 3.11 embeddable package (Windows x64):

```powershell
# Create directory
mkdir installer\embedded-python
cd installer\embedded-python

# Download Python embeddable
curl -L -o python-embed.zip "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"

# Extract
Expand-Archive python-embed.zip -DestinationPath .
Remove-Item python-embed.zip

# Download and install pip
curl -L -o get-pip.py "https://bootstrap.pypa.io/get-pip.py"
.\python.exe get-pip.py
Remove-Item get-pip.py

# IMPORTANT: Enable pip by editing python311._pth
# Remove the '#' before 'import site' line
(Get-Content python311._pth) -replace '#import site', 'import site' | Set-Content python311._pth

# Install required packages
.\python.exe -m pip install fastapi uvicorn python-dotenv httpx pydantic PyPDF2 python-docx python-pptx Pillow python-multipart aiofiles

cd ../..
```

### Step 3: Build the Frontend

```powershell
cd frontend
npm install
npm run build
cd ..
```

This creates the `frontend/dist/` folder with production-ready files.

### Step 4: Build the Electron App (Optional)

If you want the desktop wrapper:

```powershell
cd installer/electron-app
npm install
npm run build:win
cd ../..
```

This creates `installer/electron-app/dist/win-unpacked/`.

### Step 5: Create Icon File

Create or copy your application icon:

```powershell
mkdir installer\assets
# Copy your icon.ico file to installer\assets\icon.ico
```

> **Tip:** Convert PNG to ICO using online tools like [ConvertICO](https://convertico.com/)

### Step 6: Create LICENSE File

Ensure you have a LICENSE file in the root directory:

```powershell
# Create MIT license or copy your license
echo "MIT License..." > LICENSE
```

---

## Building with Inno Setup

### Step 7: Install Inno Setup

1. Download from: https://jrsoftware.org/isdl.php
2. Run the installer (accept defaults)
3. Inno Setup Compiler is now available

### Step 8: Open and Compile the Script

**Option A: GUI Method**

1. Open **Inno Setup Compiler**
2. Click **File > Open**
3. Navigate to `installer/inno-setup/llm-council-installer.iss`
4. Click **Build > Compile** (or press F9)

**Option B: Command Line**

```powershell
# Add Inno Setup to PATH or use full path
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\inno-setup\llm-council-installer.iss
```

### Step 9: Find Your Installer

The compiled installer will be at:
```
installer/output/LLMCouncil-Setup-2.0.0.exe
```

---

## Alternative: Standalone Python Launcher

If you prefer a simpler approach without Electron:

### Build PyInstaller Executable

```powershell
# Install PyInstaller
pip install pyinstaller

# Build standalone exe
cd installer/scripts
pyinstaller --onefile --windowed --icon=..\assets\icon.ico --name="LLM Council" launcher.py
```

This creates `dist/LLM Council.exe`.

---

## Testing the Installer

### Pre-Installation Test

1. Create a clean Windows VM or use Windows Sandbox
2. Copy the installer to the test environment
3. Run the installer

### Post-Installation Checklist

- [ ] Application launches from Start Menu
- [ ] Desktop shortcut works (if selected)
- [ ] Backend server starts successfully
- [ ] Web dashboard opens in browser
- [ ] Settings can be saved
- [ ] Document upload works
- [ ] API key validation works
- [ ] Uninstaller removes all files

---

## Customization

### Changing Application Name/Version

Edit `llm-council-installer.iss`:

```iss
#define MyAppName "LLM Council"
#define MyAppVersion "2.0.0"
```

### Changing Default Models

Edit `config/default_config.json`:

```json
{
  "council_models": [
    "openai/gpt-4o",
    "google/gemini-2.0-flash-exp"
  ],
  "chairman_model": "google/gemini-2.0-flash-exp"
}
```

### Adding Startup Entry

The installer already includes an optional startup task. Users can enable it during installation.

---

## Troubleshooting

### Common Issues

**Issue: "Path not found" or long path errors during Inno Setup compilation**
```
Error: Le chemin d'accès spécifié est introuvable (Path not found)
During: Compressing pkg_resources\tests\...
```

**Solution:** Run the cleanup script to remove test directories with very long paths:
```powershell
cd installer\scripts
.\cleanup_python.ps1
```

Or manually delete these directories:
```powershell
cd installer\embedded-python\Lib\site-packages
Remove-Item -Recurse -Force pkg_resources\tests
Remove-Item -Recurse -Force setuptools\tests
Remove-Item -Recurse -Force pip\tests
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -Directory -Filter tests | Remove-Item -Recurse -Force
```

**Issue: "Python not found"**
```
Solution: Ensure python311._pth is edited to enable site-packages
```

**Issue: "pip not working"**
```
Solution: Remove '#' from 'import site' in python311._pth
```

**Issue: "Backend won't start"**
```
Solution: Check if port 8001 is already in use:
netstat -an | findstr 8001
```

**Issue: "Installer too large"**
```
Solution: Clean __pycache__ folders and test directories:
.\cleanup_python.ps1
```

**Issue: "Missing OCR packages"**
```
Solution: Install easyocr and its dependencies:
.\python.exe -m pip install easyocr torch torchvision
```
Note: EasyOCR and PyTorch add ~2GB to the installer size.

### Debug Mode

To debug the installer, add to the .iss file:
```iss
[Setup]
...
SetupLogging=yes
```

Logs will be saved to %TEMP%\Setup Log*.txt

---

## Distribution

### Final Checklist

- [ ] Version numbers match everywhere
- [ ] LICENSE file is included
- [ ] README is included
- [ ] Icon file is included
- [ ] All Python packages are installed
- [ ] Frontend is built
- [ ] Installer tested on clean system

### Signing (Optional but Recommended)

For distribution, sign your installer:

```powershell
signtool sign /f your_certificate.pfx /p password /t http://timestamp.digicert.com installer\output\LLMCouncil-Setup-2.0.0.exe
```

---

## Quick Reference Commands

```powershell
# Build everything from scratch
cd llm-council

# 1. Frontend
cd frontend && npm install && npm run build && cd ..

# 2. Prepare embedded Python (see Step 2 above)

# 3. Build installer
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\inno-setup\llm-council-installer.iss

# Output: installer/output/LLMCouncil-Setup-2.0.0.exe
```

---

## Support

For issues with:
- **LLM Council app:** https://github.com/karpathy/llm-council/issues
- **Inno Setup:** https://jrsoftware.org/isinfo.php
- **Electron Builder:** https://www.electron.build/

---

*Last updated: 2025*
