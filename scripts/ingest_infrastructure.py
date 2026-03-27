
import os
import sys
import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.db import engine

CSV_PATH = r"c:\ROSH\DeepSpatial\geospatial-infra-llm\data\raw\meghalaya\infra\MDM_Infra_Report.csv"

def clean_column_name(col):
    return col.strip().lower().replace(' ', '_').replace('.', '').replace('-', '_').replace('__', '_')

def ingest_infrastructure():
    print(f"Reading CSV from {CSV_PATH}...")
    try:
        df = pd.read_csv(CSV_PATH)
    except FileNotFoundError:
        print(f"Error: File not found at {CSV_PATH}")
        return

    # 1. Clean Columns
    df.columns = [clean_column_name(c) for c in df.columns]
    
    # Rename critical columns for consistency
    rename_map = {
        'udise_code': 'udisecode',
        'school_name': 'school_name',
    }
    df.rename(columns=rename_map, inplace=True)
    
    # Ensure udisecode is string/text for joining
    df['udisecode'] = df['udisecode'].astype(str).str.split('.').str[0]
    
    print(f"Columns found: {list(df.columns)}")
    print(f"Rows: {len(df)}")
    
    # 2. Re-create Table (Drop and Create)
    table_name = "meghalaya_infrastructure"
    
    with engine.connect() as conn:
        print(f"Dropping table {table_name} if exists...")
        conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE;"))
        conn.commit()
        
    print(f"Uploading to {table_name}...")
    try:
        df.to_sql(table_name, engine, if_exists='replace', index=False)
        
        # Add primary key
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table_name} ADD PRIMARY KEY (udisecode);"))
            conn.commit()
            
        print("✅ Ingestion Data Complete!")
        
        # Verify
        with engine.connect() as conn:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            print(f"Verified row count: {count}")
            
    except Exception as e:
        print(f"Error uploading data: {e}")

if __name__ == "__main__":
    ingest_infrastructure()
