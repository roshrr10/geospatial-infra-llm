import asyncio
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from backend.services.ollama_service import get_sql_from_llm
from backend.services.spatial_service import execute_spatial_query

async def test_query(question):
    print(f"\nQuestion: {question}")
    try:
        sql, level = await get_sql_from_llm(question)
        print(f"Detected Level: {level}")
        print(f"Generated SQL:\n{sql}")
        
        result = execute_spatial_query(sql)
        row_count = len(result.get('table', []))
        print(f"Result: SUCCESS ({row_count} rows)")
        if row_count > 0:
            print(f"Sample data: {result['table'][0]}")
    except Exception as e:
        print(f"Result: FAILED - {str(e)}")

async def main():
    queries = [
        "Show West Garo Hills",
        "Blocks with low road density",
        "Schools without electricity",
        "Districts with high IFA coverage for girls",
        "Show schools with solar panels in Thadlaskein block"
    ]
    
    for q in queries:
        await test_query(q)

if __name__ == "__main__":
    asyncio.run(main())
