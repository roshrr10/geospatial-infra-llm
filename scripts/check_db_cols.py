import psycopg2

try:
    conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5433/meghalaya_geo_llm")
    cur = conn.cursor()
    cur.execute("SELECT * FROM meghalaya_infrastructure LIMIT 0;")
    cols = [desc[0] for desc in cur.description]
    print("COLUMNS:")
    for c in cols:
        print(c)
except Exception as e:
    print(e)
