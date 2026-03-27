import pandas as pd
from sqlalchemy import create_engine, text
import json

engine = create_engine("postgresql://postgres:7654@localhost:5433/meghalaya_geo_llm")

def check_structure():
    output = []
    keys = ['ramp_available', 'library_facility', 'electricity_connection_available', 'no_of_computer']
    try:
        with engine.connect() as conn:
            for k in keys:
                output.append(f"\n--- Distinct values for {k} ---")
                res = conn.execute(text(f"SELECT \"{k}\", count(*) FROM meghalaya_infrastructure GROUP BY 1")).fetchall()
                for r in res:
                    output.append(f"{r[0]}: {r[1]}")
                
        with open("db_values.txt", "w") as f:
            f.write("\n".join(output))
        print("Done. See db_values.txt")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_structure()
