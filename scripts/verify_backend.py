import sys
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.spatial_service import execute_spatial_query
from backend.database.db import engine

def test_db_connection():
    try:
        with engine.connect() as conn:
            print("Successfully connected to the database.")
    except Exception as e:
        print(f"Database connection failed: {e}")

def test_spatial_query():
    try:
        sql = "SELECT block_name, district_name, geometry FROM meghalaya_block_intelligence LIMIT 1;"
        result = execute_spatial_query(sql)
        print("Spatial query executed successfully.")
        print(f"Found {len(result['geojson']['features'])} features.")
    except Exception as e:
        print(f"Spatial query failed: {e}")

if __name__ == "__main__":
    test_db_connection()
    test_spatial_query()
