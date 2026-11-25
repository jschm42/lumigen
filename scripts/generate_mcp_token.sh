#!/usr/bin/env bash
set -euo pipefail

# Generate a bearer token for the MCP endpoint. Pass --write to store it in .env.
python "$(dirname "$0")/generate_mcp_token.py" "$@"
