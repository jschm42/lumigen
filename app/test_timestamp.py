import sqlite3
import time
from pathlib import Path

db_path = Path("c:/Users/jschmitz/DEV/git-repositories/lumigen/data/app.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT id, updated_at FROM enhancement_configs")
print(f"Before: {cursor.fetchone()}")

time.sleep(1)

cursor.execute("UPDATE enhancement_configs SET default_enhancement_prompt = ? WHERE id = 1", ("Another Test",))
# Note: sqlite doesn't automatically update a column unless there's a trigger.
# SQLAlchemy handles 'onupdate' by sending the value in the UPDATE statement.
conn.commit()

cursor.execute("SELECT id, updated_at FROM enhancement_configs")
print(f"After (SQL update): {cursor.fetchone()}")

conn.close()
