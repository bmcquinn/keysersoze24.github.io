<#
.SYNOPSIS
    Automates updates for the Soul Shell Engine deployment architecture.
.DESCRIPTION
    Stages files, handles local tracking, and pushes personal-use assets to GitHub.
#>
param (
    [Parameter(Mandatory=$true)]
    [string]$CommitMessage
)

$ErrorActionPreference = "Stop"

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "         SOUL SHELL REPOSITORY SYNC MATRIX          " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

try {
    if (-not (Test-Path .git)) {
        throw "Target directory is not a valid Git repository initialization zone."
    }

    Write-Host "Staging structural assets..." -ForegroundColor Yellow
    git add .

    Write-Host "Committing changes with signature..." -ForegroundColor Yellow
    git commit -m "$CommitMessage"

    Write-Host "Pushing payload upstream to bmcquinn/soul-shell..." -ForegroundColor Yellow
    git push origin main

    Write-Host "====================================================" -ForegroundColor Green
    Write-Host "   SYNC COMPLETE: SOUL SHELL ASSETS UPDATED LIVE    " -ForegroundColor Green
    Write-Host "====================================================" -ForegroundColor Green
}
catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Sync pipeline aborted." -ForegroundColor Red
}
