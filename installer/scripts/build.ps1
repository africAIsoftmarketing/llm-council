# LLM Council Installer - PowerShell Build Script
# Run: .\build.ps1

param(
    [switch]$SkipFrontend,
    [switch]$SkipPython,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  LLM Council Installer Build Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$RootDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$InstallerDir = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $RootDir "frontend"
$PythonDir = Join-Path $InstallerDir "embedded-python"
$OutputDir = Join-Path $InstallerDir "output"
$AssetsDir = Join-Path $InstallerDir "assets"

# Create output directory
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

# Step 1: Build Frontend
if (-not $SkipFrontend) {
    Write-Host "[1/5] Building Frontend..." -ForegroundColor Yellow
    Write-Host "----------------------------------------"
    
    Push-Location $FrontendDir
    try {
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
        
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm build failed" }
        
        Write-Host "Frontend build complete!" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "[1/5] Skipping Frontend build" -ForegroundColor Gray
}
Write-Host ""

# Step 2: Download Embedded Python
if (-not $SkipPython) {
    Write-Host "[2/5] Setting up Embedded Python..." -ForegroundColor Yellow
    Write-Host "----------------------------------------"
    
    if (-not (Test-Path $PythonDir)) {
        New-Item -ItemType Directory -Path $PythonDir | Out-Null
    }
    
    $PythonExe = Join-Path $PythonDir "python.exe"
    
    if (-not (Test-Path $PythonExe)) {
        Write-Host "Downloading Python 3.11 embeddable..."
        $PythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
        $ZipPath = Join-Path $PythonDir "python-embed.zip"
        
        Invoke-WebRequest -Uri $PythonUrl -OutFile $ZipPath
        Expand-Archive -Path $ZipPath -DestinationPath $PythonDir -Force
        Remove-Item $ZipPath
        
        Write-Host "Installing pip..."
        $GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
        $GetPipPath = Join-Path $PythonDir "get-pip.py"
        Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPipPath
        
        & $PythonExe $GetPipPath
        Remove-Item $GetPipPath
        
        # Enable site-packages
        Write-Host "Enabling site-packages..."
        $PthFile = Join-Path $PythonDir "python311._pth"
        (Get-Content $PthFile) -replace '#import site', 'import site' | Set-Content $PthFile
    }
    else {
        Write-Host "Embedded Python already exists."
    }
    
    Write-Host "Embedded Python ready!" -ForegroundColor Green
}
else {
    Write-Host "[2/5] Skipping Python download" -ForegroundColor Gray
}
Write-Host ""

# Step 3: Install Python Packages
if (-not $SkipPython) {
    Write-Host "[3/5] Installing Python Packages..." -ForegroundColor Yellow
    Write-Host "----------------------------------------"
    
    $PythonExe = Join-Path $PythonDir "python.exe"
    
    & $PythonExe -m pip install --upgrade pip
    
    # Install core packages
    Write-Host "Installing core packages..." -ForegroundColor Gray
    & $PythonExe -m pip install fastapi uvicorn python-dotenv httpx pydantic PyPDF2 python-docx python-pptx Pillow python-multipart aiofiles
    
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install core Python packages"
    }
    
    # Install OCR packages (easyocr + dependencies including torch)
    Write-Host "Installing OCR packages (easyocr, torch)... This may take a while..." -ForegroundColor Gray
    & $PythonExe -m pip install easyocr
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Failed to install OCR packages. OCR features may not work." -ForegroundColor Yellow
    }
    else {
        Write-Host "OCR packages installed successfully!" -ForegroundColor Green
    }
    
    # Clean up unnecessary files to avoid long path issues during installer build
    Write-Host "Cleaning up unnecessary files (tests, caches)..." -ForegroundColor Yellow
    
    $SitePackages = Join-Path $PythonDir "Lib\site-packages"
    if (Test-Path $SitePackages) {
        # Remove test directories (cause long path issues)
        Get-ChildItem -Path $SitePackages -Directory -Recurse -ErrorAction SilentlyContinue | 
            Where-Object { $_.Name -eq "tests" -or $_.Name -eq "test" -or $_.Name -eq "testing" } | 
            ForEach-Object { 
                Write-Host "  Removing: $($_.FullName)" -ForegroundColor Gray
                Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue 
            }
        
        # Remove __pycache__ directories
        Get-ChildItem -Path $SitePackages -Directory -Recurse -ErrorAction SilentlyContinue | 
            Where-Object { $_.Name -eq "__pycache__" } | 
            ForEach-Object { 
                Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue 
            }
        
        # Remove .pyc and .pyo files
        Get-ChildItem -Path $SitePackages -File -Recurse -ErrorAction SilentlyContinue | 
            Where-Object { $_.Extension -eq ".pyc" -or $_.Extension -eq ".pyo" } | 
            ForEach-Object { 
                Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue 
            }
        
        # Remove .egg files (problematic for long paths)
        Get-ChildItem -Path $SitePackages -File -Recurse -ErrorAction SilentlyContinue | 
            Where-Object { $_.Extension -eq ".egg" } | 
            ForEach-Object { 
                Write-Host "  Removing: $($_.FullName)" -ForegroundColor Gray
                Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue 
            }
        
        # Specifically remove pkg_resources test data (causes the error)
        $PkgResourcesTests = Join-Path $SitePackages "pkg_resources\tests"
        if (Test-Path $PkgResourcesTests) {
            Write-Host "  Removing: $PkgResourcesTests" -ForegroundColor Gray
            Remove-Item -Path $PkgResourcesTests -Recurse -Force -ErrorAction SilentlyContinue
        }
        
        # Remove setuptools test data
        $SetuptoolsTests = Join-Path $SitePackages "setuptools\tests"
        if (Test-Path $SetuptoolsTests) {
            Write-Host "  Removing: $SetuptoolsTests" -ForegroundColor Gray
            Remove-Item -Path $SetuptoolsTests -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    
    Write-Host "Python packages installed and cleaned!" -ForegroundColor Green
}
else {
    Write-Host "[3/5] Skipping Python packages" -ForegroundColor Gray
}
Write-Host ""

# Step 4: Check Assets
Write-Host "[4/5] Checking Assets..." -ForegroundColor Yellow
Write-Host "----------------------------------------"

if (-not (Test-Path $AssetsDir)) {
    New-Item -ItemType Directory -Path $AssetsDir | Out-Null
}

$IconPath = Join-Path $AssetsDir "icon.ico"
if (-not (Test-Path $IconPath)) {
    Write-Host "WARNING: icon.ico not found in assets folder" -ForegroundColor Yellow
    Write-Host "Please add an icon file before building the installer." -ForegroundColor Yellow
}
else {
    Write-Host "Icon file found." -ForegroundColor Green
}
Write-Host ""

# Step 5: Build Installer
if (-not $SkipInstaller) {
    Write-Host "[5/5] Building Installer..." -ForegroundColor Yellow
    Write-Host "----------------------------------------"
    
    $InnoPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    $IssFile = Join-Path $InstallerDir "inno-setup\llm-council-installer.iss"
    
    if (Test-Path $InnoPath) {
        Write-Host "Compiling with Inno Setup..."
        & $InnoPath $IssFile
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "============================================" -ForegroundColor Green
            Write-Host "  BUILD COMPLETE!" -ForegroundColor Green
            Write-Host "============================================" -ForegroundColor Green
            Write-Host ""
            Write-Host "Installer created at:" -ForegroundColor Cyan
            Write-Host "$OutputDir\LLMCouncil-Setup-2.0.0.exe"
        }
        else {
            throw "Inno Setup compilation failed"
        }
    }
    else {
        Write-Host "WARNING: Inno Setup not found at $InnoPath" -ForegroundColor Yellow
        Write-Host "Please install Inno Setup 6 from: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
        Write-Host "Then run this script again, or compile manually." -ForegroundColor Yellow
    }
}
else {
    Write-Host "[5/5] Skipping installer build" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
