
import asyncio
import os
import sys
import json

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.services.ollama_service import get_sql_from_llm
from backend.services.spatial_service import execute_spatial_query

async def test_specific_queries():
    queries = [
        "Show schools with no electricity connection",
        "Which schools have both computers and smart classrooms?",
        "Show schools in RI BHOI with a library facility",
        "List schools in WEST GARO HILLS with no drinking water"
    ]
    
    print(f"{'Query':<60} | {'Status':<10} | {'Count':<5}")
    print("-" * 80)
    
    for q in queries:
        try:
            print(f"\nQUERY: {q}")
            sql, level = await get_sql_from_llm(q)
            print(f"GENERATED SQL:\n{sql}\n")
            result = execute_spatial_query(sql)
            count = len(result.get('table', []))
            status = "✅" if count > 0 else "❌ Empty"
            print(f"STATUS: {status} | COUNT: {count}")
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_specific_queries())
