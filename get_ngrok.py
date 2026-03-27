import requests
import json

try:
    response = requests.get('http://127.0.0.1:4040/api/tunnels')
    if response.status_code == 200:
        data = response.json()
        public_url = data['tunnels'][0]['public_url']
        print(f"Current Ngrok Public URL: {public_url}")
    else:
        print(f"Error: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")
