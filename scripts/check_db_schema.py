from backend.database.db import engine
from sqlalchemy import text
import pandas as pd

def check_schema():
    with engine.connect() as con:
        # Check meghalaya_infrastructure table
        print("\nColumns in 'meghalaya_infrastructure':")
        r = con.execute(text("SELECT * FROM meghalaya_infrastructure LIMIT 0"))
        print(r.keys())
        
        # Check first row to see if values are 'Yes'/'No' or 1/0
        print("\nFirst row sample:")
        df = pd.read_sql("SELECT * FROM meghalaya_infrastructure LIMIT 1", engine)
        print(df.to_dict(orient='records')[0] if not df.empty else "Empty")

if __name__ == "__main__":
    check_schema()
