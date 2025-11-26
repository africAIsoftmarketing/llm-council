# LLM Council Windows Installer Package

This directory contains all the source code and scripts needed to build a Windows installer for LLM Council.

## Quick Start

On Windows, run:
```powershell
cd installer\scripts
.\build.bat
```

This will:
1. Build the frontend
2. Download embedded Python
3. Install Python dependencies
4. Create the installer (if Inno Setup is installed)

## Directory Structure

```
installer/
├── electron-app/          # Electron desktop wrapper
│   ├── package.json        # Electron dependencies
│   ├── main.js             # Main process
│   ├── preload.js          # Preload script
│   └── splash.html         # Splash screen
│
├── inno-setup/            # Inno Setup installer
│   └── llm-council-installer.iss
│
├── nsis/                  # NSIS installer (alternative)
│   └── llm-council-installer.nsi
│
├── scripts/               # Build and runtime scripts
│   ├── build.bat           # Main build script
│   ├── download_python.bat # Download embedded Python
│   ├── setup.bat           # Post-install dependency setup
│   ├── start_services.bat  # Start backend server
│   ├── stop_services.bat   # Stop services
│   ├── launch.bat          # Quick launcher
│   └── launcher.py         # Python/Tkinter GUI launcher
│
├── embedded-python/       # Python 3.11 embeddable (downloaded)
│
├── config/
│   └── default_config.json # Default configuration
│
├── assets/                # Icons and images
│   └── icon.ico            # (you need to add this)
│
├── docs/
│   ├── BUILD_GUIDE.md      # Complete build instructions
│   ├── USER_MANUAL.md      # User documentation
│   └── README_INSTALLER.txt
│
└── output/                # Compiled installer output
```

## Build Options

### Option 1: Inno Setup (Recommended)

1. Install [Inno Setup 6](https://jrsoftware.org/isdl.php)
2. Run `scripts\build.bat`
3. Find installer at `output\LLMCouncil-Setup-2.0.0.exe`

### Option 2: NSIS

1. Install [NSIS 3](https://nsis.sourceforge.io/Download)
2. Compile `nsis\llm-council-installer.nsi`

### Option 3: Electron Builder

1. `cd electron-app`
2. `npm install`
3. `npm run build:win`

### Option 4: PyInstaller (Standalone Launcher)

1. `pip install pyinstaller`
2. `pyinstaller --onefile --windowed scripts\launcher.py`

## What the Installer Does

1. **Installs Embedded Python** - No system Python required
2. **Installs All Dependencies** - FastAPI, uvicorn, etc.
3. **Creates Shortcuts** - Desktop and Start Menu
4. **Sets Up Configuration** - Default settings ready to use
5. **Enables Quick Launch** - One-click to start everything

## User Experience

After installation, users:
1. Launch "LLM Council" from Start Menu
2. Backend starts automatically
3. Browser opens to http://localhost:3000
4. Configure API key in Settings
5. Start chatting with the AI Council!

## Requirements for Building

- Windows 10/11 (64-bit)
- Node.js 18+
- Python 3.11+
- Inno Setup 6 or NSIS 3
- ~500MB disk space

## License

MIT License - See LICENSE file
