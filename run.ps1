#!/usr/bin/env pwsh
# Media Library Organization (Standalone)
# Requires Docker Desktop with Model Runner enabled

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $env:MEDIA_PATH) {
    $env:MEDIA_PATH = "C:\Users\TiHa\Data\DOWNLOADS\_Download_Extrects"
}

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host " MEDIA ORGANIZER - DOCKER MODEL RUNNER" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "MEDIA_PATH=$env:MEDIA_PATH" -ForegroundColor Gray

# Check if Docker Model Runner is running
Write-Host "Verifying Docker Model Runner status..." -ForegroundColor Cyan
docker model status | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Model Runner is not running" -ForegroundColor Red
    Write-Host "FIX: Start it with: docker model start-runner" -ForegroundColor Yellow
    exit 1
}

Write-Host "DMR is running" -ForegroundColor Green

# Check if models are available
Write-Host "Verifying models..." -ForegroundColor Cyan
docker model list | Out-Null

Write-Host "Models are available" -ForegroundColor Green
Write-Host ""

# Build container if needed
Write-Host "Building organizer container..." -ForegroundColor Cyan
docker-compose -f docker-compose.yml build media-organizer

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to build container" -ForegroundColor Red
    exit 1
}

# Run organization
Write-Host ""
Write-Host "Starting media organization..." -ForegroundColor Cyan
Write-Host ""
docker-compose -f docker-compose.yml up --abort-on-container-exit media-organizer
$runExitCode = $LASTEXITCODE

# Always cleanup the organizer container
Write-Host ""
Write-Host "Removing organizer container..." -ForegroundColor Yellow
docker-compose -f docker-compose.yml rm -f media-organizer 2>$null | Out-Null

Write-Host ""
if ($runExitCode -eq 0) {
    Write-Host "SUCCESS: Organization completed" -ForegroundColor Green
} else {
    Write-Host "ERROR: Organization failed with exit code: $runExitCode" -ForegroundColor Red
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host " COMPLETE" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

exit $runExitCode
