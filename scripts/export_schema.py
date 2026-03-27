from sqlalchemy import create_engine, inspect
import json

DB_URL = "postgresql://postgres:7654@localhost:5433/meghalaya_geo_llm"
engine = create_engine(DB_URL)
inspector = inspect(engine)

schema = {}
for table in ["meghalaya_districts", "meghalaya_blocks", "meghalaya_schools", "meghalaya_block_intelligence", "meghalaya_district_intelligence"]:
    schema[table] = [c['name'] for c in inspector.get_columns(table)]

print("SCHEMA_JSON_START")
print(json.dumps(schema, indent=2))
print("SCHEMA_JSON_END")
