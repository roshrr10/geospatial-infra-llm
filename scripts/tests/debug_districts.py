
import sys
import os
import pandas as pd

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.db import engine

def check_districts():
    print("Checking District Names Overlap...")
    
    q1 = "SELECT DISTINCT district_name FROM hp_block_infra_intelligence ORDER BY district_name;"
    districts_infra = pd.read_sql(q1, engine)['district_name'].tolist()
    
    q2 = "SELECT DISTINCT district_name FROM hp_district_boundary ORDER BY district_name;"
    districts_bound = pd.read_sql(q2, engine)['district_name'].tolist()
    
    print(f"Infra Districts ({len(districts_infra)}): {districts_infra}")
    print(f"Boundary Districts ({len(districts_bound)}): {districts_bound}")
    
    common = set(districts_infra).intersection(set(districts_bound))
    print(f"Common: {len(common)}")
    
    missing_in_bound = set(districts_infra) - set(districts_bound)
    print(f"In Infra but missing in Boundary: {missing_in_bound}")

    missing_in_infra = set(districts_bound) - set(districts_infra)
    print(f"In Boundary but missing in Infra: {missing_in_infra}")

if __name__ == "__main__":
    check_districts()
