
import os
import sys
from sqlalchemy import text

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.db import engine

def clean_tables():
    print("Cleaning ALL spatial tables...")
    with engine.begin() as conn:
        # 1. District Table
        print("Cleaning meghalaya_district_intelligence_final...")
        conn.execute(text("UPDATE meghalaya_district_intelligence_final SET district_name = TRIM(UPPER(split_part(district_name, '-', 1)))"))
        
        # 2. Block Table
        print("Cleaning meghalaya_block_intelligence_final...")
        conn.execute(text("UPDATE meghalaya_block_intelligence_final SET district_name = TRIM(UPPER(split_part(district_name, '-', 1))), block_name = TRIM(UPPER(split_part(block_name, '-', 1)))"))
        
        # 3. Schools Table (Review)
        print("Cleaning meghalaya_schools...")
        conn.execute(text("UPDATE meghalaya_schools SET district_name = TRIM(UPPER(split_part(district_name, '-', 1))), block_name = TRIM(UPPER(split_part(block_name, '-', 1)))"))
        
        # 4. Infrastructure Table
        print("Cleaning meghalaya_infrastructure...")
        conn.execute(text("UPDATE meghalaya_infrastructure SET district_name = TRIM(UPPER(split_part(district_name, '-', 1))), block_name = TRIM(UPPER(split_part(block_name, '-', 1)))"))

    print("✅ All tables cleaned!")

def list_cols():
    print("\nInfrastructure Columns:")
    import pandas as pd
    df = pd.read_sql("SELECT * FROM meghalaya_infrastructure LIMIT 0", engine)
    cols = sorted(list(df.columns))
    with open("infra_columns.txt", "w") as f:
        f.write(", ".join(cols))
    print("Saved to infra_columns.txt")

if __name__ == "__main__":
    clean_tables()
    list_cols()
