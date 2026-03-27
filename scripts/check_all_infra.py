
import os
import sys
import pandas as pd
from sqlalchemy import text

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.db import engine

def check_all_infra():
    cols = [
        'computer_room', 'library_facility', 'playground_available', 
        'ramp_available', 'drinking_water_availability', 'medical_facilities', 
        'solar_panel', 'internet_facility_available_in_school', 
        'smart_classroom_available_in_school', 'eletricity_connection_available',
        'boy_toilet_available', 'girls_toilet_available'
    ]
    
    with open("infra_values.txt", "w") as f:
        f.write("Column | Values\n")
        f.write("-" * 30 + "\n")
        for c in cols:
            try:
                query = f"SELECT DISTINCT \"{c}\" FROM meghalaya_infrastructure"
                df = pd.read_sql(query, engine)
                vals = [str(v) for v in df.iloc[:,0].unique()]
                f.write(f"{c} | {', '.join(vals)}\n")
            except Exception as e:
                f.write(f"{c} | Error: {e}\n")

if __name__ == "__main__":
    check_all_infra()
