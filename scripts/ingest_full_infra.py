
import os
import sys
import pandas as pd
from sqlalchemy import text

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.db import engine

CSV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "infrastructure.csv"))

def clean_column_name(col):
    if not isinstance(col, str):
        return str(col)
    # Remove brackets and content inside
    col = col.split('(')[0]
    # Replace newlines
    col = col.replace('\n', ' ')
    # standard cleaning
    clean = col.strip().lower().replace(' ', '_').replace('.', '').replace('/', '_').replace('-', '_')
    # Remove double underscores
    while '__' in clean:
        clean = clean.replace('__', '_')
    return clean

def ingest():
    print("Reading CSV...")
    try:
        df = pd.read_csv(CSV_PATH)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Clean & Deduplicate Columns
    used_names = set()
    new_cols = []
    
    for c in df.columns:
        clean = clean_column_name(c)
        if not clean: # handle empty
            clean = "col"
        
        candidate = clean
        counter = 1
        # Check against ALL previously assigned names
        while candidate in used_names:
            candidate = f"{clean}_{counter}"
            counter += 1
            
        used_names.add(candidate)
        new_cols.append(candidate)
    
    df.columns = new_cols
    
    # Rename key columns for consistency
    if 'udisecode' in df.columns:
        df = df.rename(columns={'udisecode': 'udise_code'})
    if 'schname' in df.columns:
        df = df.rename(columns={'schname': 'school_name'})
    if 'district_name' not in df.columns and 'district' in df.columns:
        df = df.rename(columns={'district': 'district_name'})
    
    # Ensure udise_code is string and clean
    if 'udise_code' in df.columns:
        df['udise_code'] = df['udise_code'].astype(str).str.split('.').str[0]
    else:
        print("Error: udise_code column not found after cleaning.")
        # Try to find it manually
        candidates = [c for c in df.columns if 'udise' in c]
        print(f"Candidates: {candidates}")
        return

    # Clean District and Block Names (Remove suffixes like '-1707')
    if 'district_name' in df.columns:
        df['district_name'] = df['district_name'].astype(str).str.split('-').str[0].str.strip().str.upper()
    if 'block_name' in df.columns:
        df['block_name'] = df['block_name'].astype(str).str.split('-').str[0].str.strip().str.upper()

    # Drop Sl. No if exists
    if 'sl_no' in df.columns:
        df = df.drop(columns=['sl_no'])
        
    print(f"Columns to ingest: {list(df.columns)}")
    print(f"Rows: {len(df)}")
    
    # Write to DB
    table_name = "meghalaya_infrastructure"
    print(f"Writing to table {table_name}...")
    
    with engine.begin() as conn:
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_udise ON {table_name} (udise_code)"))
        
        print("Cleaning meghalaya_schools names...")
        conn.execute(text("UPDATE meghalaya_schools SET district_name = split_part(district_name, '-', 1), block_name = split_part(block_name, '-', 1)"))
        conn.execute(text("UPDATE meghalaya_schools SET district_name = TRIM(UPPER(district_name)), block_name = TRIM(UPPER(block_name))"))
        
    print("✅ Ingestion & Cleaning Complete!")

if __name__ == "__main__":
    ingest()
