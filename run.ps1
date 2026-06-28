# Start script for Lumigen (Windows PowerShell)
$ErrorActionPreference = "Stop"

# Change directory to the script's directory
Set-Location -Path $PSScriptRoot

# 1. Check if setup has been completed
if (-not (Test-Path -Path ".setup_done" -PathType Leaf)) {
    Write-Host "=========================================" -ForegroundColor Yellow
    Write-Host "Warning: Lumigen has not been set up yet!" -ForegroundColor Yellow
    Write-Host "=========================================" -ForegroundColor Yellow
    $response = Read-Host "Would you like to run setup.ps1 now? [Y/n]"
    if ([string]::IsNullOrWhiteSpace($response) -or $response.ToLower() -eq "y" -or $response.ToLower() -eq "yes") {
        Write-Host "Starting setup..."
        # Run setup with bypassed execution policy to avoid permission errors
        powershell -ExecutionPolicy Bypass -File .\setup.ps1
    } else {
        $runAnyway = Read-Host "Would you like to try starting the application anyway? [y/N]"
        if ($runAnyway.ToLower() -ne "y" -and $runAnyway.ToLower() -ne "yes") {
            Write-Host "Exiting."
            exit 0
        }
    }
}

# 2. Pull latest changes from Git before execution
if (Get-Command git -ErrorAction SilentlyContinue) {
    if (Test-Path -Path ".git" -PathType Container) {
        Write-Host "Pulling latest changes from Git..."
        try {
            git pull
        } catch {
            Write-Warning "git pull failed. Starting application with local files."
        }
    }
} else {
    Write-Host "git command not found. Skipping pull."
}

# 3. Start the application
if (Test-Path -Path ".venv" -PathType Container) {
    Write-Host "Activating virtual environment..."
    . .venv\Scripts\Activate.ps1
    Write-Host "Starting Lumigen..." -ForegroundColor Green
    python -m app.main
} else {
    Write-Error "Virtual environment (.venv) not found. Please run setup first."
    exit 1
}
