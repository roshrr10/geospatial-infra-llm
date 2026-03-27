
import sys
import os
import pandas as pd

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.db import engine
from backend.nlq.sql_generator import generate_sql

def test_single():
    print("Testing Medium Districts Query ONLY")
    q = "Which districts have medium road connectivity?"
    
    # 1. Generate SQL
    result = generate_sql(q)
    print(f"Query: {q}")
    print(f"Level: {result['level']}")
    print(f"SQL: {result['sql'].strip()}")
    
    if result['level'] != "district":
        print("FAIL: Level is not district")
        return

    # 2. Execute SQL
    try:
        df = pd.read_sql(result['sql'], engine)
        print(f"Main Query Rows: {len(df)}")
        if len(df) > 0:
            print(f"Districts Found: {df['district_name'].tolist()}")
    except Exception as e:
        print(f"Main SQL Error: {e}")
        return

    if len(df) == 0:
        print("FAIL: No rows returned")
        return

    # 3. Geometry Logic
    districts = df['district_name'].unique().tolist()
    safe_districts = []
    for x in districts:
        clean = x.replace("'", "''")
        safe_districts.append(f"'{clean}'")
    in_clause = ", ".join(safe_districts)
    
    geom_sql = f"""
    SELECT
        d.district_name AS name,
        ST_AsGeoJSON(d.geom) AS geometry
    FROM hp_district_boundary d
    JOIN (
        SELECT district_name,
                AVG(road_connectivity_score) AS road_connectivity_score
        FROM hp_block_infra_intelligence
        GROUP BY district_name
    ) i
    ON d.district_name = i.district_name
    WHERE d.district_name IN ({in_clause});
    """
    
    try:
        geo_df = pd.read_sql(geom_sql, engine)
        print(f"Geometry Query Rows: {len(geo_df)}")
        if len(geo_df) < len(df):
            print("WARNING: Geometry rows < Main rows (Checking Mismatch)")
            found_names = geo_df['name'].tolist()
            missing = set(districts) - set(found_names)
            print(f"Missing Districts: {missing}")
    except Exception as e:
        print(f"Geometry SQL Error: {e}")

if __name__ == "__main__":
    test_single()
