#!/usr/bin/env bash
# Start script for Lumigen (Linux / macOS)
set -euo pipefail

# Change directory to the script's directory
cd "$(dirname "${BASH_SOURCE[0]}")"

# 1. Check if setup has been completed
if [ ! -f ".setup_done" ]; then
    echo "========================================="
    echo "Warning: Lumigen has not been set up yet!"
    echo "========================================="
    read -r -p "Would you like to run setup.sh now? [Y/n]: " response
    response=${response,,} # convert to lowercase
    if [[ "$response" =~ ^(yes|y|)$ ]]; then
        echo "Starting setup..."
        chmod +x setup.sh
        ./setup.sh
    else
        read -r -p "Would you like to try starting the application anyway? [y/N]: " run_anyway
        run_anyway=${run_anyway,,}
        if [[ ! "$run_anyway" =~ ^(yes|y)$ ]]; then
            echo "Exiting."
            exit 1
        fi
    fi
fi

# 2. Pull latest changes from Git before execution
if command -v git &> /dev/null && [ -d .git ]; then
    echo "Pulling latest changes from Git..."
    git pull || echo "Warning: git pull failed. Starting application with local files."
else
    echo "Not a Git repository or git command not found. Skipping pull."
fi

# 3. Start the application
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
    echo "Starting Lumigen..."
    python -m app.main
else
    echo "Error: Virtual environment (.venv) not found. Please run setup first."
    exit 1
fi
