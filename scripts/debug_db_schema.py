
import sys
import os
from sqlalchemy import inspect, text

# Fix path to import backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.db import engine

def debug_schema():
    inspector = inspect(engine)
    try:
        table_names = inspector.get_table_names()
        print(f"Tables in database '{engine.url.database}':")
        for table in table_names:
            try:
                with engine.connect() as conn:
                    count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                print(f"- {table}: {count} rows")
                
                # Print columns for key tables
                if "meghalaya" in table or "hp_" in table:
                    columns = inspector.get_columns(table)
                    col_names = [col['name'] for col in columns]
                    print(f"  Columns: {col_names}")
            except Exception as e:
                print(f"- {table}: Error getting count ({e})")
                
    except Exception as e:
        print(f"Error inspecting DB: {e}")

if __name__ == "__main__":
    debug_schema()
