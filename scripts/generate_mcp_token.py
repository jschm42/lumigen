"""Generate a bearer token for Lumigen's MCP endpoint (/mcp).

Usage (from the repository root):
    python scripts/generate_mcp_token.py           # print a new token
    python scripts/generate_mcp_token.py --write   # also set MCP_API_TOKEN in .env

Restart Lumigen after changing .env. Clients send the token as
``Authorization: Bearer <token>``.
"""
from __future__ import annotations

import argparse
import re
import secrets
from pathlib import Path

ENV_KEY = "MCP_API_TOKEN"
TOKEN_BYTES = 32


def generate_token() -> str:
    """Return a new URL-safe random token (256 bits)."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def write_token(env_path: Path, token: str) -> bool:
    """Set ``MCP_API_TOKEN`` in *env_path*, replacing an existing entry.

    Returns:
        True if an existing entry was replaced, False if the line was appended.
    """
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    line = f"{ENV_KEY}={token}"
    pattern = re.compile(rf"^{ENV_KEY}=.*$", re.MULTILINE)
    if pattern.search(text):
        env_path.write_text(pattern.sub(line, text, count=1), encoding="utf-8")
        return True
    separator = "" if not text or text.endswith("\n") else "\n"
    env_path.write_text(f"{text}{separator}{line}\n", encoding="utf-8")
    return False


def main() -> None:
    """Parse arguments, generate the token and print or store it."""
    parser = argparse.ArgumentParser(description="Generate a bearer token for Lumigen's MCP endpoint.")
    parser.add_argument("--write", action="store_true", help=f"set {ENV_KEY} in the .env file")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="path to the .env file (default: .env)")
    args = parser.parse_args()

    token = generate_token()
    if not args.write:
        print(token)
        return
    replaced = write_token(args.env_file, token)
    action = "Replaced" if replaced else "Added"
    print(f"{action} {ENV_KEY} in {args.env_file}. Restart Lumigen to apply it.")
    print(f"Token for your MCP client: {token}")


if __name__ == "__main__":
    main()
