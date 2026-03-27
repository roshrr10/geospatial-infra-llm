import requests

url = "https://elois-rowable-nonexpressively.ngrok-free.dev/api/spatial/basemap?level=district"
try:
    print(f"Fetching: {url}")
    response = requests.get(url, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Success! Features count: {len(data.get('features', []))}")
    else:
        print(f"Content: {response.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
