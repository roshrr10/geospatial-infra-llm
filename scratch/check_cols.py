from sqlalchemy import create_engine, inspect
import os

engine = create_engine("postgresql://postgres:postgres@localhost:5432/meghalaya_spatial")
inspector = inspect(engine)

print("District Intelligence Columns:")
columns = inspector.get_columns('meghalaya_district_intelligence_final')
for column in columns:
    print(column['name'])

print("\nInfrastructure Columns:")
columns = inspector.get_columns('meghalaya_infrastructure')
for column in columns:
    print(column['name'])
