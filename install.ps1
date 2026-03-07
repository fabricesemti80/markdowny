$ErrorActionPreference = 'Stop'

Write-Host "Installing prerequisites for docflux..." -ForegroundColor Cyan

# Check for pandoc
if (-not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
    Write-Host "Installing pandoc via winget..." -ForegroundColor Yellow
    winget install --id JohnMacFarlane.Pandoc -e --accept-source-agreements --accept-package-agreements
    # Refresh PATH so pandoc is available in this session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
} else {
    Write-Host "pandoc found." -ForegroundColor Green
}

# Check for uv
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    # Refresh PATH so uv is available in this session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
} else {
    Write-Host "uv found." -ForegroundColor Green
}

# Ensure we are in the right directory
if (Test-Path "pyproject.toml") {
    Write-Host "Installing from local directory..." -ForegroundColor Cyan
} else {
    Write-Host "Downloading docflux..." -ForegroundColor Yellow
    $installDir = Join-Path $env:TEMP "docflux-install"
    if (Test-Path $installDir) { Remove-Item $installDir -Recurse -Force }
    New-Item -ItemType Directory -Path $installDir | Out-Null

    $zipPath = Join-Path $installDir "docflux.zip"
    Invoke-WebRequest -Uri "https://github.com/fabricesemti80/docflux/archive/refs/heads/main.zip" -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $installDir -Force
    Set-Location (Join-Path $installDir "docflux-main")
}

Write-Host "Installing Python 3.12 (required for PDF support)..." -ForegroundColor Cyan
uv python install 3.12

Write-Host "Installing docflux with PDF support..." -ForegroundColor Cyan
uv tool install --native-tls --python 3.12 .

Write-Host ""
Write-Host "Done! You can now run: dfx <input.md> [output]" -ForegroundColor Green
