# Builds a Windows executable with PyInstaller.
# This script is provided for packaging; the produced .exe was not visually
# verified in the development environment (no PowerPoint/LibreOffice installed).

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Create it first: py -3.11 -m venv .venv"
}

& $python -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name SlideBridge `
    --collect-all pymupdf `
    --collect-data pptx `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

Write-Host ""
Write-Host "Build complete: $root\dist\SlideBridge\SlideBridge.exe"
Write-Host "Test the executable on a clean Windows machine before distribution."
