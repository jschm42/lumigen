#!/usr/bin/env bash
set -euo pipefail

python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
