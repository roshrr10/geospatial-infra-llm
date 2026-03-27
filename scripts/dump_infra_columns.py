from backend.database.db import engine
from sqlalchemy import text

def dump_columns():
    with engine.connect() as con:
        r = con.execute(text("SELECT * FROM meghalaya_infrastructure LIMIT 0"))
        cols = r.keys()
        with open("infra_columns_full.txt", "w") as f:
            for col in cols:
                f.write(col + "\n")
        print(f"Dumped {len(cols)} columns to infra_columns_full.txt")

if __name__ == "__main__":
    dump_columns()
