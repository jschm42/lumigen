# Setup script for Lumigen (Windows PowerShell)
$ErrorActionPreference = "Stop"

# Change directory to the script's directory
Set-Location -Path $PSScriptRoot

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Starting Lumigen Setup..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Pull latest changes from Git
if (Get-Command git -ErrorAction SilentlyContinue) {
    if (Test-Path -Path ".git" -PathType Container) {
        Write-Host "Pulling latest changes from Git..."
        try {
            git pull
        } catch {
            Write-Warning "git pull failed. Continuing setup with local files."
        }
    }
} else {
    Write-Host "git command not found. Skipping pull."
}

# 2. Create virtual environment if it doesn't exist
if (-not (Test-Path -Path ".venv" -PathType Container)) {
    Write-Host "Creating virtual environment (.venv)..."
    python -m venv .venv
}

# 3. Activate virtual environment
Write-Host "Activating virtual environment..."
& .venv\Scripts\Activate.ps1

# 4. Install Python dependencies
Write-Host "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Configure environment (.env)
if (-not (Test-Path -Path ".env" -PathType Leaf)) {
    Write-Host "Creating .env from .env.example..."
    Copy-Item -Path ".env.example" -Destination ".env"
    
    # Generate secret keys
    python -c @"
import secrets
try:
    from cryptography.fernet import Fernet
    fernet_key = Fernet.generate_key().decode()
except ImportError:
    fernet_key = ''
    print('Warning: cryptography package not found. PROVIDER_CONFIG_KEY not set.')

with open('.env', 'r') as f:
    content = f.read()

content = content.replace('SESSION_SECRET_KEY=', 'SESSION_SECRET_KEY=' + secrets.token_hex(32))
if fernet_key:
    content = content.replace('PROVIDER_CONFIG_KEY=', 'PROVIDER_CONFIG_KEY=' + fernet_key)

with open('.env', 'w') as f:
    f.write(content)
"@
    Write-Host ".env file created with generated security keys." -ForegroundColor Green
} else {
    Write-Host ".env file already exists. Skipping creation."
}

# 6. Run database migrations
Write-Host "Running database migrations..."
alembic upgrade head

# 7. Install Node dependencies and Playwright if npm is available
if (Get-Command npm.cmd -ErrorAction SilentlyContinue) {
    Write-Host "Installing Node dependencies..."
    try {
        npm.cmd ci
    } catch {
        npm.cmd install
    }
    
    Write-Host "Installing Playwright browsers..."
    npx.cmd playwright install --with-deps chromium
} elseif (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "Installing Node dependencies..."
    try {
        npm ci
    } catch {
        npm install
    }
    
    Write-Host "Installing Playwright browsers..."
    npx playwright install --with-deps chromium
} else {
    Write-Warning "npm not found. Skipping Node and Playwright setup."
}

# 8. Create marker file
Write-Host "Creating setup marker file..."
"Setup completed on $(Get-Date)" | Out-File -FilePath ".setup_done" -Encoding utf8

Write-Host "=========================================" -ForegroundColor Green
Write-Host "Setup completed successfully!" -ForegroundColor Green
Write-Host "You can now start the application with .\run.ps1" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
