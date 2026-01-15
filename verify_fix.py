import requests
import sys

try:
    print("Testing /api/health...")
    r = requests.get("http://127.0.0.1:8000/api/health")
    print(f"Health Status: {r.status_code}")
    print(r.text)

    print("\nTesting /api/auth/register (expecting 400 or 422, not 500)...")
    r = requests.post("http://127.0.0.1:8000/api/auth/register", json={
        "email": "invalid-email",
        "password": "short",
        "full_name": "Test"
    })
    print(f"Register Status: {r.status_code}")
    print(r.text)

    if r.status_code >= 500:
        print("FAIL: Still getting 500 error")
        sys.exit(1)
    else:
        print("SUCCESS: Server handled request without crashing")

except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)
