import sys
import os
sys.path.append(os.getcwd())

from backend.database.db import engine
from sqlalchemy import text
import pandas as pd

def sync():
    with engine.connect() as conn:
        print("Starting final block synchronization in root...")
        
        # 1. Get census data
        census = pd.read_sql(text("SELECT block_name, district_name, count(*) as count FROM meghalaya_schools GROUP BY block_name, district_name"), conn)
        print(f"Total Census blocks from schools: {len(census)}")
        
        # 2. Sync loop
        for _, row in census.iterrows():
            b = row['block_name']
            d = row['district_name']
            c = row['count']
            
            # Simple check and update/insert
            res = conn.execute(text("SELECT id FROM meghalaya_block_intelligence_final WHERE block_name = :b"), {"b": b}).fetchone()
            if res:
                conn.execute(text("UPDATE meghalaya_block_intelligence_final SET total_schools = :c WHERE block_name = :b"), {"b": b, "c": c})
            else:
                print(f"Inserting missing block: {b}")
                conn.execute(text("INSERT INTO meghalaya_block_intelligence_final (block_name, district_name, total_schools, schools_per_sqkm) VALUES (:b, :d, :c, 0)"), {"b": b, "d": d, "c": c})
        
        conn.commit()
        
        # 3. Recalc density
        conn.execute(text("UPDATE meghalaya_block_intelligence_final SET schools_per_sqkm = CASE WHEN geometry IS NOT NULL AND ST_Area(geometry::geography) > 0 THEN total_schools / (ST_Area(geometry::geography) / 1000000.0) ELSE 0 END"))
        conn.commit()
        
        # 4. Final verification
        final_count = conn.execute(text("SELECT count(*) FROM meghalaya_block_intelligence_final")).fetchone()[0]
        print(f"Final Count in Intelligence Table: {final_count}")

if __name__ == "__main__":
    sync()
