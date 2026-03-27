
import os
import sys
import pandas as pd
from sqlalchemy import text

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.db import engine
from backend.services.spatial_service import execute_spatial_query

def debug():
    sql = "SELECT district_name, avg_ifa_coverage_girls, avg_deworm_coverage_girls FROM meghalaya_district_intelligence_final ORDER BY avg_ifa_coverage_girls ASC LIMIT 5;"
    print(f"Testing SQL: {sql}")
    
    try:
        result = execute_spatial_query(sql)
        print("Success!")
        print(result)
    except Exception as e:
        print(f"Error executing query: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug()
