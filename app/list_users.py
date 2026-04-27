import sqlite3
from pathlib import Path

db_path = Path("c:/Users/jschmitz/DEV/git-repositories/lumigen/data/app.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT id, username, role FROM users")
print(cursor.fetchall())

conn.close()
