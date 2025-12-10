
import requests
import json
import time

url = "http://localhost:8000/rag-query"
payload = {"text": "Hello"}
headers = {"Content-Type": "application/json"}

print("Waiting for server to be ready...")
for i in range(10):
    try:
        requests.get("http://localhost:8000/health", timeout=2)
        print("Server is up!")
        break
    except:
        time.sleep(1)

try:
    print(f"Sending request to {url}...")
    # Timeout 30s because AI model loading might be slow first time
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    print(f"Status Code: {response.status_code}")
    print("Response JSON:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Request failed: {e}")
