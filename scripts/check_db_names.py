
import os
import sys
import pandas as pd
from sqlalchemy import text

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.db import engine

def check_names():
    print("Checking District Names:")
    try:
        df = pd.read_sql("SELECT DISTINCT district_name FROM meghalaya_district_intelligence_final", engine)
        print(df)
    except Exception as e:
        print(f"Error accessing district table: {e}")

    print("\nChecking Block Names:")
    try:
        df = pd.read_sql("SELECT DISTINCT block_name, district_name FROM meghalaya_block_intelligence_final LIMIT 10", engine)
        print(df)
    except Exception as e:
        print(f"Error accessing block table: {e}")

    print("\nChecking School District Names:")
    try:
        df = pd.read_sql("SELECT DISTINCT district_name FROM meghalaya_schools LIMIT 10", engine)
        print(df)
    except Exception as e:
        print(f"Error accessing schools table: {e}")

    print("\nChecking Infrastructure Columns:")
    try:
        df = pd.read_sql("SELECT * FROM meghalaya_infrastructure LIMIT 1", engine)
        print(df.columns.tolist())
    except Exception as e:
        print(f"Error accessing infra table: {e}")

if __name__ == "__main__":
    check_names()
