from sqlalchemy import text
from backend.database.db import engine

with engine.connect() as conn:
    r = conn.execute(text("SELECT schlocation, COUNT(*) as count FROM meghalaya_infrastructure GROUP BY schlocation"))
    for row in r:
        print(f"{row.schlocation}: {row.count}")
