#!/usr/bin/env bash
# Setup script for Lumigen (Linux / macOS)
set -euo pipefail

# Change directory to the script's directory
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "========================================="
echo "Starting Lumigen Setup..."
echo "========================================="

# 1. Pull latest changes from Git
if command -v git &> /dev/null && [ -d .git ]; then
    echo "Pulling latest changes from Git..."
    git pull || echo "Warning: git pull failed. Continuing setup with local files."
else
    echo "Not a Git repository or git command not found. Skipping pull."
fi

# 2. Determine Python command
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python is not installed. Please install Python 3.12+."
    exit 1
fi

# 3. Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment (.venv)..."
    $PYTHON_CMD -m venv .venv
fi

# 4. Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# 5. Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 6. Configure environment (.env)
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    
    # Generate secret keys
    python -c "
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
"
    echo ".env file created with generated security keys."
else
    echo ".env file already exists. Skipping creation."
fi

# 7. Run database migrations
echo "Running database migrations..."
alembic upgrade head

# 8. Install Node dependencies and Playwright if npm is available
if command -v npm &> /dev/null; then
    echo "Installing Node dependencies..."
    npm ci || npm install
    
    echo "Installing Playwright browsers..."
    npx playwright install --with-deps chromium
else
    echo "Warning: npm is not installed. Skipping Node and Playwright setup."
fi

# 9. Create marker file
echo "Creating setup marker file..."
echo "Setup completed on $(date)" > .setup_done

echo "========================================="
echo "Setup completed successfully!"
echo "You can now start the application with ./run.sh"
echo "========================================="
