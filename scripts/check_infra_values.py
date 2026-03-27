
import os
import sys
import pandas as pd
from sqlalchemy import text

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.db import engine

def check_values():
    cols = [
        'eletricity_connection_available', 
        'drinking_water_availability', 
        'library_facility', 
        'computer_room', 
        'smart_classroom_available_in_school',
        'internet_facility_available_in_school'
    ]
    
    print("Checking Unique Values for key columns:")
    for col in cols:
        try:
            query = f"SELECT DISTINCT \"{col}\" FROM meghalaya_infrastructure"
            df = pd.read_sql(query, engine)
            print(f"\nCol: {col}")
            print(df)
        except Exception as e:
            print(f"Error checking {col}: {e}")

if __name__ == "__main__":
    check_values()
