
import sys
import os
import pandas as pd
import json

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.db import engine
from backend.nlq.sql_generator import generate_sql

def test_logic(user_query):
    print(f"Testing query: '{user_query}'")
    
    # 1. Generate SQL
    result = generate_sql(user_query)
    level = result["level"]
    sql = result["sql"]
    print(f"Level: {level}")
    # print(f"SQL: {sql}")

    # 2. Execute SQL
    try:
        df = pd.read_sql(sql, engine)
    except Exception as e:
        print(f"Initial Query Failed: {e}")
        return

    print(f"Rows returned: {len(df)}")
    if len(df) == 0:
        print("Empty result. Geometry query would fail if not handled.")
        return

    # 3. Geometry SQL Construction
    if level == "block":
        # Simulate app.py logic exactly (the buggy version)
        # geom_sql = f"... WHERE b.block_name IN {tuple(df['block_name'])};"
        
        # Construct exact string
        block_names = tuple(df['block_name'])
        in_clause = str(block_names)
        
        # Fix for single element tuple representation which app.py might rely on default str()
        print(f"IN clause string: {in_clause}")
        
        geom_sql = f"""
        SELECT
            b.block_name AS name,
            b.district_name,
            i.total_schools,
            i.road_connectivity_score,
            ST_AsGeoJSON(b.geom) AS geometry
        FROM hp_block_boundary b
        JOIN hp_block_infra_intelligence i
        ON b.block_name = i.block_name
        WHERE b.block_name IN {in_clause};
        """
        
    elif level == "district":
        districts = tuple(df['district_name'].unique())
        in_clause = str(districts)
        print(f"IN clause string: {in_clause}")
        
        geom_sql = f"""
        SELECT
            d.district_name AS name,
            i.road_connectivity_score,
            ST_AsGeoJSON(d.geom) AS geometry
        FROM hp_district_boundary d
        JOIN (
            SELECT district_name,
                   AVG(road_connectivity_score) AS road_connectivity_score
            FROM hp_block_infra_intelligence
            GROUP BY district_name
            HAVING AVG(road_connectivity_score) > 0 # Simplifying join logic for test
        ) i
        ON d.district_name = i.district_name
        WHERE d.district_name IN {in_clause};
        """

    else:
        print("Unknown level")
        return

    # 4. Execute Geometry SQL
    try:
        geo_df = pd.read_sql(geom_sql, engine)
        print(f"Geometry rows: {len(geo_df)}")
    except Exception as e:
        print(f"Geometry SQL Failed: {e}")

if __name__ == "__main__":
    queries = [
        "Which blocks have good road connectivity?",
        "Which districts have medium road connectivity?", 
        "Show me areas with poor road connectivity" # Should return 24
    ]
    
    for q in queries:
        test_logic(q)
        print("-" * 30)
