
import os
import sys
import pandas as pd
from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.db import engine

def check_nutrition():
    print("Checking Nutrition Data in 'meghalaya_district_intelligence_final'...")
    try:
        query = """
        SELECT 
            district_name, 
            avg_ifa_coverage_girls, 
            avg_ifa_coverage_boys, 
            avg_deworm_coverage_girls, 
            avg_deworm_coverage_boys
        FROM meghalaya_district_intelligence_final
        LIMIT 10;
        """
        df = pd.read_sql(query, engine)
        if df.empty:
            print("❌ Table is empty or not found.")
        else:
            print(df)
            
            # Check for non-null count
            print("\nNon-Null Counts:")
            print(df.count())
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_nutrition()
