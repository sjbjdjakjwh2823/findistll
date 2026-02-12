import os
import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from app.services.market_data import market_data_service

logger = logging.getLogger(__name__)

class FedShockAnalyzer:
    """Analyzer for Federal Reserve policy shocks and their micro-economic impact."""

    def __init__(self):
        # Beta values from FinDistill v17.0 Logic
        self.industry_betas = {
            "Automotive": Decimal("2.4"),
            "Industrial": Decimal("2.4"),
            "Aerospace & Defense": Decimal("2.4"),
            "Technology": Decimal("0.8"),
            "IT Platform": Decimal("0.8"),
            "Financial Services": Decimal("-1.5"),
            "General Corporate": Decimal("1.2")
        }

    async def calculate_shock_impact(self, industry: str, current_value: Decimal, shock_bps: int = 100) -> Dict[str, Any]:
        """
        Calculate the impact of a Fed rate shock (in basis points) on a specific metric value.
        Formula: impact = current_value * (1 - (beta * shock_bps / 10000))
        """
        beta = self.industry_betas.get(industry, self.industry_betas["General Corporate"])
        
        # shock_factor = (beta * bps) / 10000  (e.g., 2.4 * 100 / 10000 = 0.024 or 2.4%)
        shock_factor = (beta * Decimal(str(shock_bps))) / Decimal("10000")
        
        # For most industries (beta > 0), a rate hike (shock) is negative.
        # For Financial Services (beta < 0), it's positive.
        impact_value = current_value * (Decimal("1") - shock_factor)
        
        # Fetch real-time context
        rates = await market_data_service.get_key_rates()
        fed_funds = rates.get("fed_funds", {}).get("value", "N/A")
        
        return {
            "industry": industry,
            "beta": float(beta),
            "shock_bps": shock_bps,
            "original_value": float(current_value),
            "impact_value": float(impact_value),
            "change_pct": float(-shock_factor * 100),
            "real_time_context": {
                "current_fed_funds": fed_funds,
                "as_of": rates.get("fed_funds", {}).get("date")
            }
        }

    def get_scenario_text(self, impact_data: Dict[str, Any], metric_name: str) -> str:
        """Generate a professional scenario analysis text."""
        ctx = impact_data["real_time_context"]
        return (
            f"[Scenario: Fed Shock +{impact_data['shock_bps']}bps]\n"
            f"Given the current Fed Funds Rate of {ctx['current_fed_funds']}% (as of {ctx['as_of']}), "
            f"a projected {impact_data['shock_bps']}bp hike would impact {metric_name} by {impact_data['change_pct']:+.2f}%. "
            f"Projected {metric_name} would decrease to ${impact_data['impact_value']:,.2f}B "
            f"based on the {impact_data['industry']} sector's sensitivity beta (β_ir: {impact_data['beta']})."
        )

# Singleton
fed_shock_analyzer = FedShockAnalyzer()
