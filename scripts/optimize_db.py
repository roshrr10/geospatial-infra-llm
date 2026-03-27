"""
GEOAI-OPT-01: Create spatial indexes and optimize database performance.
Run once: python scripts/optimize_db.py
"""
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:7654@localhost:5433/meghalaya_geo_llm"
engine = create_engine(DATABASE_URL)
import time

INDEXES = [
    # Spatial indexes (GiST) on geometry columns
    ("idx_district_geom", "meghalaya_district_intelligence_final", "geometry", "GIST"),
    ("idx_block_geom", "meghalaya_block_intelligence_final", "geometry", "GIST"),
    ("idx_school_geom", "meghalaya_schools", "geometry", "GIST"),

    # B-tree indexes for join/filter columns
    ("idx_district_name_district", "meghalaya_district_intelligence_final", "district_name", "BTREE"),
    ("idx_block_name_block", "meghalaya_block_intelligence_final", "block_name", "BTREE"),
    ("idx_district_name_block", "meghalaya_block_intelligence_final", "district_name", "BTREE"),
    ("idx_block_name_school", "meghalaya_schools", "block_name", "BTREE"),
    ("idx_district_name_school", "meghalaya_schools", "district_name", "BTREE"),
    ("idx_udise_infra", "meghalaya_infrastructure", "udise_code", "BTREE"),
]

def create_indexes():
    with engine.connect() as conn:
        for idx_name, table, column, idx_type in INDEXES:
            try:
                if idx_type == "GIST":
                    sql = f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table} USING GIST ({column});'
                else:
                    sql = f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({column});'
                print(f"  Creating {idx_type} index: {idx_name} on {table}({column})...", end=" ")
                t0 = time.time()
                conn.execute(text(sql))
                conn.commit()
                print(f"OK ({time.time()-t0:.2f}s)")
            except Exception as e:
                print(f"SKIP ({e})")

def analyze_tables():
    tables = [
        "meghalaya_district_intelligence_final",
        "meghalaya_block_intelligence_final",
        "meghalaya_schools",
        "meghalaya_infrastructure",
    ]
    with engine.connect() as conn:
        for table in tables:
            print(f"  ANALYZE {table}...", end=" ")
            t0 = time.time()
            conn.execute(text(f"ANALYZE {table};"))
            conn.commit()
            print(f"OK ({time.time()-t0:.2f}s)")

def verify():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename LIKE 'meghalaya_%'
            ORDER BY tablename, indexname;
        """))
        rows = result.fetchall()
        print(f"\n  Total indexes on meghalaya_* tables: {len(rows)}")
        for r in rows:
            print(f"    {r[1]}.{r[0]}")

if __name__ == "__main__":
    print("=" * 50)
    print("GEOAI-OPT-01: Database Optimization")
    print("=" * 50)

    print("\n[1/3] Creating indexes...")
    create_indexes()

    print("\n[2/3] Analyzing tables...")
    analyze_tables()

    print("\n[3/3] Verifying indexes...")
    verify()

    print("\nDone!")
