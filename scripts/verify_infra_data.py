
import os
import sys
import pandas as pd
from sqlalchemy import text

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.db import engine

def verify_data():
    print("Verifying Infrastructure Data...")
    # SQL using correct columns: udise_code, eletricity_connection_available
    sql = """
        SELECT udise_code, eletricity_connection_available, drinking_water_availability
        FROM meghalaya_infrastructure 
        LIMIT 5;
    """
    try:
        df = pd.read_sql(sql, engine)
        print("✅ Success! Data sample:")
        print(df)
        print(f"\nColumns: {list(df.columns)}")
        
        if 'eletricity_connection_available' in df.columns:
            print("Verified 'eletricity' column exists.")
        
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    verify_data()
