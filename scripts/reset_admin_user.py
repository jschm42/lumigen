from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import crud
from app.db.engine import SessionLocal, init_db
from app.services.auth_service import AuthService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or reset an admin user password."
    )
    parser.add_argument(
        "--username",
        default="admin",
        help="Admin username to create/update (default: admin)",
    )
    parser.add_argument(
        "--password",
        default="",
        help="Admin password (if omitted, prompt securely)",
    )
    return parser.parse_args()


def _resolve_password(raw_password: str) -> str:
    if raw_password.strip():
        return raw_password

    first = getpass.getpass("New admin password: ")
    second = getpass.getpass("Repeat admin password: ")
    if first != second:
        raise ValueError("Passwords do not match")
    return first


def main() -> int:
    args = _parse_args()
    username = (args.username or "").strip()
    if len(username) < 3:
        print("Error: username must be at least 3 characters", file=sys.stderr)
        return 2

    try:
        password = _resolve_password(args.password)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    auth_service = AuthService()
    try:
        password_hash = auth_service.hash_password(password)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    init_db()

    with SessionLocal() as session:
        user = crud.get_user_by_username(session, username)
        if user is None:
            crud.create_user(
                session,
                username=username,
                password_hash=password_hash,
                role="admin",
                is_active=True,
            )
            print(f"Created admin user '{username}'.")
            return 0

        crud.update_user(
            session,
            user,
            password_hash=password_hash,
            role="admin",
            is_active=True,
        )
        print(f"Reset admin user '{username}' (password updated, role=admin, active=true).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
