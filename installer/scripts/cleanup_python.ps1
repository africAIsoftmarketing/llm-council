# LLM Council - Python Packages Cleanup Script
# Run this BEFORE building the installer if you already have embedded-python set up
# This removes test directories and other files that cause long path issues on Windows

param(
    [string]$PythonDir = $null
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Python Packages Cleanup Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Determine Python directory
if (-not $PythonDir) {
    $InstallerDir = Split-Path -Parent $PSScriptRoot
    $PythonDir = Join-Path $InstallerDir "embedded-python"
}

if (-not (Test-Path $PythonDir)) {
    Write-Host "ERROR: Python directory not found at: $PythonDir" -ForegroundColor Red
    exit 1
}

$SitePackages = Join-Path $PythonDir "Lib\site-packages"

if (-not (Test-Path $SitePackages)) {
    Write-Host "ERROR: site-packages not found at: $SitePackages" -ForegroundColor Red
    exit 1
}

Write-Host "Cleaning up: $SitePackages" -ForegroundColor Yellow
Write-Host ""

$removedCount = 0
$removedSize = 0

# Function to safely remove items
function Remove-ItemSafely {
    param([string]$Path)
    
    try {
        if (Test-Path $Path) {
            $size = (Get-ChildItem $Path -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
            Remove-Item -Path $Path -Recurse -Force -ErrorAction Stop
            return $size
        }
    }
    catch {
        # Try using cmd.exe for stubborn paths
        try {
            if (Test-Path $Path) {
                cmd /c "rd /s /q `"$Path`"" 2>$null
            }
        }
        catch {
            Write-Host "  WARNING: Could not remove $Path" -ForegroundColor Yellow
        }
    }
    return 0
}

# 1. Remove test directories
Write-Host "[1/6] Removing test directories..." -ForegroundColor Yellow
$testDirs = Get-ChildItem -Path $SitePackages -Directory -Recurse -ErrorAction SilentlyContinue | 
    Where-Object { $_.Name -eq "tests" -or $_.Name -eq "test" -or $_.Name -eq "testing" }

foreach ($dir in $testDirs) {
    Write-Host "  Removing: $($dir.Name) in $($dir.Parent.Name)" -ForegroundColor Gray
    $removedSize += Remove-ItemSafely -Path $dir.FullName
    $removedCount++
}

# 2. Remove __pycache__ directories
Write-Host "[2/6] Removing __pycache__ directories..." -ForegroundColor Yellow
$cacheDirs = Get-ChildItem -Path $SitePackages -Directory -Recurse -ErrorAction SilentlyContinue | 
    Where-Object { $_.Name -eq "__pycache__" }

foreach ($dir in $cacheDirs) {
    $removedSize += Remove-ItemSafely -Path $dir.FullName
    $removedCount++
}
Write-Host "  Removed $($cacheDirs.Count) __pycache__ directories" -ForegroundColor Gray

# 3. Remove .pyc and .pyo files
Write-Host "[3/6] Removing compiled Python files (.pyc, .pyo)..." -ForegroundColor Yellow
$compiledFiles = Get-ChildItem -Path $SitePackages -File -Recurse -ErrorAction SilentlyContinue | 
    Where-Object { $_.Extension -eq ".pyc" -or $_.Extension -eq ".pyo" }

foreach ($file in $compiledFiles) {
    $removedSize += $file.Length
    Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
    $removedCount++
}
Write-Host "  Removed $($compiledFiles.Count) compiled files" -ForegroundColor Gray

# 4. Remove .egg files
Write-Host "[4/6] Removing .egg files..." -ForegroundColor Yellow
$eggFiles = Get-ChildItem -Path $SitePackages -File -Recurse -ErrorAction SilentlyContinue | 
    Where-Object { $_.Extension -eq ".egg" }

foreach ($file in $eggFiles) {
    Write-Host "  Removing: $($file.Name)" -ForegroundColor Gray
    $removedSize += $file.Length
    Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
    $removedCount++
}

# 5. Remove specific problematic directories
Write-Host "[5/6] Removing known problematic directories..." -ForegroundColor Yellow

$problematicPaths = @(
    "pkg_resources\tests",
    "setuptools\tests", 
    "pip\tests",
    "pip\_vendor\tests",
    "torch\test",
    "torch\testing",
    "torch\_inductor\test",
    "torchvision\tests",
    "numpy\tests",
    "numpy\core\tests",
    "numpy\lib\tests",
    "scipy\tests",
    "cv2\data",
    "easyocr\scripts"
)

foreach ($relPath in $problematicPaths) {
    $fullPath = Join-Path $SitePackages $relPath
    if (Test-Path $fullPath) {
        Write-Host "  Removing: $relPath" -ForegroundColor Gray
        $removedSize += Remove-ItemSafely -Path $fullPath
        $removedCount++
    }
}

# 6. Remove stub packages (type hints, not needed at runtime)
Write-Host "[6/6] Removing type stub packages..." -ForegroundColor Yellow
$stubDirs = Get-ChildItem -Path $SitePackages -Directory -ErrorAction SilentlyContinue | 
    Where-Object { $_.Name -like "*-stubs" }

foreach ($dir in $stubDirs) {
    Write-Host "  Removing: $($dir.Name)" -ForegroundColor Gray
    $removedSize += Remove-ItemSafely -Path $dir.FullName
    $removedCount++
}

# Summary
$sizeInMB = [math]::Round($removedSize / 1MB, 2)

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Cleanup Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Items removed: $removedCount" -ForegroundColor Cyan
Write-Host "Space freed: ~$sizeInMB MB" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now run the Inno Setup build." -ForegroundColor Green
