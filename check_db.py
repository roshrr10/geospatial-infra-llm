import sys
sys.path.append('.')
from backend.database.db import engine
import pandas as pd

try:
    tables = pd.read_sql("SELECT table_name FROM information_schema.tables WHERE table_schema='public'", engine)
    print("Tables in database:")
    print(tables)
    
    for table in ['meghalaya_schools', 'meghalaya_infrastructure', 'meghalaya_district_intelligence_final', 'meghalaya_block_intelligence_final']:
        if table in tables['table_name'].values:
            count = pd.read_sql(f"SELECT count(*) FROM {table}", engine).iloc[0,0]
            print(f"Table {table}: {count} rows")
        else:
            print(f"Table {table}: MISSING")
except Exception as e:
    print(f"Error: {e}")
