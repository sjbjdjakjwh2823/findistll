import pytest
from dotenv import load_dotenv
import os

# Load env before importing services that use it
load_dotenv()

import asyncio
from app.services.market_data import market_data_service

@pytest.mark.asyncio
async def test_fred_integration():
    print("🚀 Testing FRED API Integration...")
    
    # Load env from .env file
    load_dotenv()
    
    rates = await market_data_service.get_key_rates()
    
    if not rates:
        print("❌ Failed to fetch rates. Check API key and connectivity.")
        return

    print("✅ Rates fetched successfully:")
    for label, data in rates.items():
        print(f"  - {label} ({data['series_id']}): {data['value']} (as of {data['date']})")

if __name__ == "__main__":
    # Ensure we are in the project root to load .env
    os.chdir("/Users/leesangmin/Desktop/preciso")
    asyncio.run(test_fred_integration())
