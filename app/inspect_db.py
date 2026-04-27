import sqlite3
from pathlib import Path

db_path = Path("c:/Users/jschmitz/DEV/git-repositories/lumigen/data/app.db")
if not db_path.exists():
    print(f"DB not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(enhancement_configs)")
    columns = cursor.fetchall()
    for col in columns:
        print(col)
    
    cursor.execute("SELECT * FROM enhancement_configs")
    rows = cursor.fetchall()
    print(f"Rows: {rows}")
    conn.close()
