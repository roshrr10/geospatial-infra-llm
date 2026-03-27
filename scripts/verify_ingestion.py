from sqlalchemy import create_engine, text
import pandas as pd

DB_URL = "postgresql://postgres:7654@localhost:5433/meghalaya_geo_llm"
engine = create_engine(DB_URL)

def verify():
    try:
        with engine.connect() as conn:
            # Check table existence and count
            res = conn.execute(text("SELECT count(*) FROM meghalaya_infrastructure")).scalar()
            print(f"Verified: meghalaya_infrastructure count = {res}")
            
            # Check a few rows
            df = pd.read_sql("SELECT udisecode, schname, district_name FROM meghalaya_infrastructure LIMIT 5", engine)
            print("Sample Data:")
            print(df)
    except Exception as e:
        print(f"Verification Failed: {e}")

if __name__ == "__main__":
    verify()
