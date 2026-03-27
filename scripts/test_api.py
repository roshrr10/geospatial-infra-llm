
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_endpoint(name, url, method="GET", payload=None):
    print(f"\n--- Testing {name} ---")
    print(f"URL: {url}")
    try:
        if method == "GET":
            response = requests.get(url)
        else:
            response = requests.post(url, json=payload)
            
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # print snippet
            if isinstance(data, list):
                print(f"Response (List): {len(data)} items")
                print(json.dumps(data[:1], indent=2))
            elif isinstance(data, dict):
                keys = list(data.keys())
                print(f"Response (Dict Keys): {keys}")
                if "table" in data:
                    print(f"Table Rows: {len(data['table'])}")
                    if len(data['table']) > 0:
                        print("Sample Row:", data['table'][0])
                if "geojson" in data and data['geojson']:
                    print(f"GeoJSON Type: {data['geojson'].get('type', 'Unknown')}")
                    if "features" in data['geojson']:
                        print(f"GeoJSON Features: {len(data['geojson']['features'])}")
                else:
                    print("GeoJSON: None or missing")
        else:
            print("Error Response:", response.text)
            
    except Exception as e:
        print(f"Request Failed: {e}")

if __name__ == "__main__":
    # 1. Test Basemap
    test_endpoint("Basemap (District)", f"{BASE_URL}/basemap?level=district")
    
    # 2. Test Simple Query
    test_endpoint("Query: Districts", f"{BASE_URL}/query", "POST", {"question": "Show all districts"})
    
    # 3. Test Complex Query
    test_endpoint("Query: Nutrition Priority", f"{BASE_URL}/query", "POST", {"question": "Which districts should be top priority for nutrition?"})
