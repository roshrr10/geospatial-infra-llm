import requests
import json

url = "http://localhost:8000/query"
payload = {"question": "Show high risk blocks"}
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, timeout=60)
    print(f"Status: {response.status_code}")
    if response.status_code != 200:
        print(f"Error Detail: {response.text}")
    else:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
