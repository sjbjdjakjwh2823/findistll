import sys
import os
import asyncio

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
                    os.environ[key] = value
        print("Loaded .env file manually.")
    else:
        print("No .env file found.")

# Load environment variables first
load_env_manual()

# SIMULATE THE ERROR: Set URL without protocol to test auto-fix
print("Simulating error condition: SUPABASE_URL missing protocol")
os.environ["SUPABASE_URL"] = "findistill.supabase.co"
# Alternatively, to test missing protocol:
# os.environ["SUPABASE_URL"] = "findistill.supabase.co"

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

    print("Attempting to send registration request...")
    try:
        transport = ASGITransport(app=app)
        # We use a base_url for the client, but the app uses internal logic to call Supabase
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/auth/register", json={
                "email": "debug_test@example.com",
                "password": "password123",
                "full_name": "Debug User"
            })
            print(f"\nResponse Code: {response.status_code}")
            print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"Request execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
