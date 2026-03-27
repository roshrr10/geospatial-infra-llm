import httpx
import asyncio
import json

async def test_query(question):
    print(f"\n TESTING: {question}")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("http://127.0.0.1:8000/query", json={"question": question}, timeout=120.0)
            if response.status_code == 200:
                data = response.json()
                if data.get("type") == "chat":
                    print(f"  [CHAT] {data.get('message')}")
                else:
                    table = data.get("table", [])
                    print(f"  [SUCCESS] Rows returned: {len(table)}")
                    if table:
                        print(f"  Sample Row: {json.dumps(table[0], indent=2)}")
            else:
                print(f"  [ERROR] Status {response.status_code}: {response.text}")
        except Exception as e:
            print(f"  [FAILED] {e}")

async def main():
    queries = [
        "Which schools have both computers and smart classrooms?",
        "List schools in WEST GARO HILLS with no drinking water",
        "Show schools that need ramp facilities",
        "Show schools in RI BHOI with a library facility"
    ]
    for q in queries:
        await test_query(q)

if __name__ == "__main__":
    asyncio.run(main())
