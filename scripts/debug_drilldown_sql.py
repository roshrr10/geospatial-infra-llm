
import os
import sys
from sqlalchemy import text
import pandas as pd

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.db import engine

def debug_sql():
    block_name = "THADLASKEIN"
    sql = f"""
            SELECT s.*, 
                   i.electricity_connection_available, i.drinking_water_availability, 
                   i.library_facility, i.computer_room, i.playground_available, 
                   i.ramp_available, i.internet_facility_available_in_school,
                   i.boy_toilet_available, i.girls_toilet_available,
                   i.solar_panel, i.rainwater_harvesting
            FROM meghalaya_schools s 
            LEFT JOIN meghalaya_infrastructure i ON s."udiseCode" = i.udise_code 
            WHERE s.block_name = '{block_name}';
    """
    print("Executing SQL:")
    print(sql)
    
    try:
        with engine.connect() as conn:
            # Try loading with geopandas
            import geopandas as gpd
            import json
            gdf = gpd.read_postgis(sql, conn, geom_col="geometry")
            print("GeoPandas Load Successful!")
            print(gdf.head())
            print(gdf.dtypes)
            
            print("Testing to_json...")
            json_str = gdf.to_json()
            print("to_json Successful! Length:", len(json_str))
            
            print("Testing json.loads...")
            data = json.loads(json_str)
            print("json.loads Successful!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_sql()
