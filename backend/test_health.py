import requests
try:
    r = requests.get("http://127.0.0.1:8000/health")
    print(f"127.0.0.1 status: {r.status_code}")
    print(r.json())
except Exception as e:
    print(f"127.0.0.1 error: {e}")

try:
    r = requests.get("http://localhost:8000/health")
    print(f"localhost status: {r.status_code}")
except Exception as e:
    print(f"localhost error: {e}")
