import sys
import os
import asyncio
import random
import string

# Manual .env loading
def load_env_manual():
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = value
        print("Loaded .env file manually.")
    else:
        print("No .env file found.")

# Load environment variables first
load_env_manual()

# Ensure SUPABASE_URL is set for the test (if not in env) or modify if needed to test the fix
# For this test, we want to rely on the .env values or the fix we implemented.
# Note: we are NOT deleting SUPABASE_URL here.

# Add current directory to sys.path
sys.path.append(os.getcwd())

async def main():
    print("Trying to import api.app...")
    try:
        from api.app import app
        from httpx import AsyncClient, ASGITransport
        print("Successfully imported app.")
    except Exception as e:
        print(f"CRITICAL: Failed to import api.app: {e}")
        import traceback
        traceback.print_exc()
        return

    # Generate random user for testing to avoid conflict
    rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    test_email = f"user{rand_suffix}@test.com"
    test_password = "TestPassword123!"
    test_name = f"Test User {rand_suffix}"

    print(f"\n--- Testing Authentication for: {test_email} ---")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            
            # 1. Test Registration
            print(f"\n[1] Attempting Registration...")
            response = await ac.post("/api/auth/register", json={
                "email": test_email,
                "password": test_password,
                "full_name": test_name
            })
            
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                print("Registration Success!")
                data = response.json()
                print(f"Got Access Token: {data.get('access_token')[:20]}...")
            else:
                print(f"Registration Failed: {response.text}")
                # Use verify_fix.py logic? No, just stop here if reg fails
                return

            # 2. Test Login
            print(f"\n[2] Attempting Login...")
            response = await ac.post("/api/auth/login", json={
                "email": test_email,
                "password": test_password
            })
            
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                print("Login Success!")
                data = response.json()
                print(f"Got Access Token: {data.get('access_token')[:20]}...")
            else:
                print(f"Login Failed: {response.text}")

    except Exception as e:
        print(f"Request execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
