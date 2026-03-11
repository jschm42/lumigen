from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove dummy chat sessions created for UI testing."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/app.db"),
        help="Path to sqlite database file",
    )
    parser.add_argument(
        "--prefix",
        default="dummy-session",
        help="Token prefix used in chat_session_id values",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete rows. Without this flag, only show a dry-run summary.",
    )
    return parser.parse_args()


def extract_token(raw_snapshot: str | None) -> str | None:
    if not raw_snapshot:
        return None
    try:
        snapshot = json.loads(raw_snapshot)
    except (json.JSONDecodeError, TypeError):
        return None
    token = snapshot.get("chat_session_id")
    return token if isinstance(token, str) else None


def main() -> int:
    args = parse_args()
    db_path = args.db
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    generation_ids: list[int] = []
    cur.execute("SELECT id, request_snapshot_json FROM generations")
    for row in cur.fetchall():
        token = extract_token(row["request_snapshot_json"])
        if isinstance(token, str) and token.startswith(f"{args.prefix}:"):
            generation_ids.append(int(row["id"]))

    cur.execute("SELECT chat_session_id FROM chat_sessions")
    pref_ids: list[str] = []
    for row in cur.fetchall():
        token = row["chat_session_id"]
        if isinstance(token, str) and token.startswith(f"{args.prefix}:"):
            pref_ids.append(token)

    print(
        "Cleanup preview:",
        f"generations={len(generation_ids)}",
        f"chat_sessions={len(pref_ids)}",
        f"prefix={args.prefix}",
    )

    if not args.apply:
        print("Dry-run only. Re-run with --apply to delete these rows.")
        conn.close()
        return 0

    if generation_ids:
        cur.executemany("DELETE FROM generations WHERE id = ?", [(item,) for item in generation_ids])
    if pref_ids:
        cur.executemany(
            "DELETE FROM chat_sessions WHERE chat_session_id = ?",
            [(item,) for item in pref_ids],
        )

    conn.commit()
    conn.close()
    print("Cleanup complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
