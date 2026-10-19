import sqlite3
from pathlib import Path

db_path = Path("c:/Users/jschmitz/DEV/git-repositories/lumigen/data/app.db")
if not db_path.exists():
    print(f"DB not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    for table_name_tuple in tables:
        table_name = table_name_tuple[0]
        print(f"\nTable: {table_name}")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col}")
    conn.close()
