
import os
import sys
from sqlalchemy import text
import pandas as pd

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.db import engine

def verify_fix():
    print("Verifying 'eletricity' column...")
    sql = """
        SELECT udisecode, eletricity_connection_available 
        FROM meghalaya_infrastructure 
        LIMIT 5;
    """
    try:
        df = pd.read_sql(sql, engine)
        print("✅ Success! Columns found:")
        print(df)
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    verify_fix()
