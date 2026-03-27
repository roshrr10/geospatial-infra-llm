from sqlalchemy import create_engine
import pandas as pd

DB_URL = "postgresql://postgres:7654@localhost:5433/meghalaya_geo_llm"
engine = create_engine(DB_URL)

tables = [
    "meghalaya_blocks", "meghalaya_districts", "meghalaya_schools",
    "meghalaya_block_infra", "meghalaya_block_health",
    "meghalaya_block_intelligence", "meghalaya_district_intelligence"
]

print("--- Data Population Audit ---")
for t in tables:
    try:
        df = pd.read_sql(f"SELECT * FROM {t} LIMIT 1", engine) # Just to check columns
        count = pd.read_sql(f"SELECT count(*) FROM {t}", engine).iloc[0,0]
        print(f"Table: {t:35} | Count: {count:6}")
        if count > 0:
            # Check for generic column nullity in block_intelligence
            if t == "meghalaya_block_intelligence":
                nulls = pd.read_sql("SELECT count(*) FROM meghalaya_block_intelligence WHERE avg_ifa_coverage_girls IS NULL", engine).iloc[0,0]
                print(f"  -> avg_ifa_coverage_girls NULL count: {nulls}")
    except Exception as e:
        print(f"Table: {t:35} | MISSING or ERROR: {e}")
