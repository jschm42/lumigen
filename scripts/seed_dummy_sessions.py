from __future__ import annotations

import argparse
import json
import random
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed dummy generations that appear as chat sessions in the UI."
    )
    parser.add_argument("--count", type=int, default=100, help="Number of sessions to create")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/app.db"),
        help="Path to sqlite database file",
    )
    parser.add_argument(
        "--prefix",
        default="dummy-session",
        help="Token prefix used for generated chat_session_id values",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic timestamps",
    )
    return parser.parse_args()


def to_storage_dt(value: datetime) -> str:
    # Store UTC timestamps in the same textual form SQLite commonly receives.
    return value.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S.%f")


def main() -> int:
    args = parse_args()
    if args.count <= 0:
        print("Nothing to do: --count must be > 0")
        return 0

    db_path = args.db
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT request_snapshot_json FROM generations")
    existing_tokens: set[str] = set()
    for row in cur.fetchall():
        raw_snapshot = row["request_snapshot_json"]
        if not raw_snapshot:
            continue
        try:
            snapshot = json.loads(raw_snapshot)
        except (json.JSONDecodeError, TypeError):
            continue
        token = snapshot.get("chat_session_id")
        if isinstance(token, str) and token.startswith(f"{args.prefix}:"):
            existing_tokens.add(token)

    rng = random.Random(args.seed)
    now = datetime.now(UTC)
    inserted = 0
    skipped = 0

    sql = """
    INSERT INTO generations (
        profile_id,
        profile_name,
        prompt_user,
        prompt_final,
        provider,
        model,
        status,
        error,
        profile_snapshot_json,
        storage_template_snapshot_json,
        request_snapshot_json,
        failure_sidecar_path,
        created_at,
        finished_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    for idx in range(1, args.count + 1):
        token = f"{args.prefix}:{idx:03d}"
        if token in existing_tokens:
            skipped += 1
            continue

        # Distribute sessions between ~3 and ~360 days old.
        days_ago = 3 + int((idx - 1) * (357 / max(args.count - 1, 1)))
        created = now - timedelta(
            days=days_ago,
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
            seconds=rng.randint(0, 59),
        )
        finished = created + timedelta(seconds=rng.randint(1, 8))

        request_snapshot = {
            "chat_session_id": token,
            "chat_session_title": f"Dummy Session {idx:03d}",
        }

        cur.execute(
            sql,
            (
                None,
                f"Dummy Profile {idx:03d}",
                f"Dummy prompt for session {idx:03d}",
                f"Dummy final prompt for session {idx:03d}",
                "dummy",
                "dummy-model",
                "succeeded",
                None,
                json.dumps({}, separators=(",", ":")),
                json.dumps({}, separators=(",", ":")),
                json.dumps(request_snapshot, separators=(",", ":")),
                None,
                to_storage_dt(created),
                to_storage_dt(finished),
            ),
        )
        inserted += 1

    conn.commit()
    conn.close()

    print(
        f"Dummy session seed complete. Inserted: {inserted}, skipped existing: {skipped}, prefix: {args.prefix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
