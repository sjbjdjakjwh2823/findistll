import pytest
from dotenv import load_dotenv
import os

# Load env
load_dotenv()

import asyncio
from decimal import Decimal
from app.services.oracle import fed_shock_analyzer

@pytest.mark.asyncio
async def test_oracle_alignment():
    print("🚀 Testing Oracle Fed Shock Alignment...")
    
    # Simulate an Automotive company with 10B Net Income
    industry = "Automotive"
    net_income = Decimal("10.0") # 10B
    
    impact = await fed_shock_analyzer.calculate_shock_impact(industry, net_income, shock_bps=50) # 50bp shock
    
    print(f"✅ Shock Impact Calculated for {industry}:")
    print(f"  - Original: ${impact['original_value']}B")
    print(f"  - Beta: {impact['beta']}")
    print(f"  - Impact Value: ${impact['impact_value']}B")
    print(f"  - Change: {impact['change_pct']}%")
    
    scenario = fed_shock_analyzer.get_scenario_text(impact, "Net Income")
    print("\n📄 Generated Scenario Text:")
    print(scenario)
