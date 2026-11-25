$ErrorActionPreference = "Stop"

# Generate a bearer token for the MCP endpoint. Pass --write to store it in .env.
python "$PSScriptRoot\generate_mcp_token.py" @args
