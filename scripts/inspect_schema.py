from sqlalchemy import create_engine, text
import pandas as pd

DB_URL = "postgresql://postgres:7654@localhost:5433/meghalaya_geo_llm"
engine = create_engine(DB_URL)

def inspect():
    tables = ['meghalaya_block_intelligence_final', 'meghalaya_district_intelligence_final', 'meghalaya_infrastructure', 'meghalaya_schools']
    for table in tables:
        print(f"\n--- Schema for {table} ---")
        try:
            df = pd.read_sql(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'", engine)
            print(df)
        except Exception as e:
            print(f"Error inspecting {table}: {e}")

if __name__ == "__main__":
    inspect()
