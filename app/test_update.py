import sqlite3
from pathlib import Path

db_path = Path("c:/Users/jschmitz/DEV/git-repositories/lumigen/data/app.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Before update:")
cursor.execute("SELECT id, default_enhancement_prompt FROM enhancement_configs")
print(cursor.fetchone())

cursor.execute("UPDATE enhancement_configs SET default_enhancement_prompt = ? WHERE id = 1", ("Test Prompt",))
conn.commit()

print("After update:")
cursor.execute("SELECT id, default_enhancement_prompt FROM enhancement_configs")
print(cursor.fetchone())

conn.close()
