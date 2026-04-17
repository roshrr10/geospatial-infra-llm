
import requests
import json

BASE_URL = "http://localhost:8000"
QUERY = "Which schools have both computers and smart classrooms?"

def test_venn_query():
    print(f"\n--- Testing Full-Spectrum Venn-Logic ---")
    print(f"Query: {QUERY}")
    
    payload = {"question": QUERY}
    try:
        response = requests.post(f"{BASE_URL}/query", json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # 1. Inspect SQL
            sql = data.get("sql", "").strip()
            print("\nGenerated SQL:")
            print(sql)
            
            # Verify NO WHERE filter (for full spectrum)
            upper_sql = sql.upper()
            has_where = "WHERE" in upper_sql and "I.NO_OF_COMPUTER" in upper_sql
            has_status = "STATUS" in upper_sql or "CASE" in upper_sql
            
            if not has_where:
                print("[SUCCESS] SQL returns full dataset (no restrictive filter).")
            else:
                print("[WARNING] SQL might still be filtering results.")
                
            if has_status:
                print("[SUCCESS] SQL includes calculated 'status' column.")
            else:
                print("[FAILURE] SQL missing calculated 'status' column.")
            
            # 2. Inspect Data
            table = data.get("table", [])
            print(f"\nTotal Dataset Count: {len(table)}")
            if len(table) > 0:
                keys = list(table[0].keys())
                print("Sample Data keys:", keys)
                if 'status' in keys:
                    statuses = set(row.get('status') for row in table[:100])
                    print("Sample Statuses found:", statuses)

            # 3. Inspect AI Summary
            print("\nFetching AI Summary Analysis...")
            summary_payload = {"question": QUERY, "data": table}
            summary_res = requests.post(f"{BASE_URL}/query/summary", json=summary_payload)
            
            if summary_res.status_code == 200:
                summary_data = summary_res.json().get("summary", {})
                if isinstance(summary_data, str):
                   try: summary_data = json.loads(summary_data)
                   except: pass
                
                print(json.dumps(summary_data, indent=2))
                
                # Verify formatting
                sum_points = summary_data.get("summary", [])
                if isinstance(sum_points, list) and len(sum_points) == 3:
                    print("[SUCCESS] Summary has exactly 3 points.")
                else:
                    print(f"[FAILURE] Summary format mismatch.")
            else:
                print(f"[FAILURE] Summary endpoint error: {summary_res.text}")
            
        else:
            print("Error:", response.text)
            
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    test_venn_query()
