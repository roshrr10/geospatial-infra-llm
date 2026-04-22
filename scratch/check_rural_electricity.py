from sqlalchemy import text
from backend.database.db import engine

with engine.connect() as conn:
    r = conn.execute(text("""
        SELECT i.electricity_connection_available, COUNT(*) as count 
        FROM meghalaya_infrastructure i
        WHERE i.schlocation = 'Rural'
        GROUP BY i.electricity_connection_available
    """))
    for row in r:
        print(f"Electricity {row.electricity_connection_available}: {row.count}")
