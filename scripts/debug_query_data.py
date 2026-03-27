import requests
import json

def test_query():
    url = "http://127.0.0.1:8000/query"
    payload = {"question": "Show 5 schools with electricity"}
    
    try:
        r = requests.post(url, json=payload)
        data = r.json()
        print(f"Status: {r.status_code}")
        if "table" in data and len(data["table"]) > 0:
            print("First 2 rows of table data:")
            print(json.dumps(data["table"][:2], indent=2))
        else:
            print("No table data returned")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_query()
