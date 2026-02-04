from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services.oracle import OracleEngine
from app.services.oracle_engine import DynamicCausalEngine

logger = logging.getLogger(__name__)

@dataclass
class GlobalMarketState:
    region_id: str  # US, EU, JP, CN, KR
    central_bank_rate: float = 0.0
    geopolitical_risk_index: float = 0.0
    fx_volatility_index: float = 0.0
    last_updated_at: Optional[str] = None

class GlobalInterconnectednessEngine:
    """
    Phase 5.0 Alpha: Global Interconnectedness Mapping Engine.
    Extends the Oracle capability to manage cross-market contagion paths 
    between US, Europe, and Asia.
    """

    def __init__(self, oracle: Optional[OracleEngine] = None) -> None:
        self._oracle = oracle or OracleEngine()
        self._market_states: Dict[str, GlobalMarketState] = {
            "US": GlobalMarketState(region_id="US"),
            "EU": GlobalMarketState(region_id="EU"),
            "JP": GlobalMarketState(region_id="JP"),
            "CN": GlobalMarketState(region_id="CN"),
            "KR": GlobalMarketState(region_id="KR"),
        }
        # Pre-defined cross-market exposure channels
        self._exposure_channels = [
            "rates", "fx", "credit", "liquidity", "supply_chain", "geopolitics"
        ]

    def update_regional_state(
        self, 
        region_id: str, 
        rate: Optional[float] = None,
        gpr: Optional[float] = None,
        fxv: Optional[float] = None
    ) -> None:
        if region_id not in self._market_states:
            self._market_states[region_id] = GlobalMarketState(region_id=region_id)
        
        state = self._market_states[region_id]
        if rate is not None: state.central_bank_rate = float(rate)
        if gpr is not None: state.geopolitical_risk_index = float(gpr)
        if fxv is not None: state.fx_volatility_index = float(fxv)
        state.last_updated_at = datetime.now(timezone.utc).isoformat()

    def get_global_contagion_graph(self) -> Dict[str, Any]:
        """
        Generates a graph representation of global interconnectedness 
        including current regional stress levels.
        """
        nodes = []
        for region, state in self._market_states.items():
            nodes.append({
                "id": f"market_{region.lower()}",
                "type": "market",
                "label": f"{region} Market",
                "region": region,
                "weight": self._calculate_market_weight(state),
                "attributes": {
                    "rate": state.central_bank_rate,
                    "gpr": state.geopolitical_risk_index,
                    "fxv": state.fx_volatility_index
                }
            })
        
        # In a real implementation, these edges would come from Exposure table/NOTEARS
        # For Alpha, we define structural global links
        links = self._get_structural_global_links()
        
        return {
            "metadata": {
                "version": "v5.0-alpha",
                "snapshot_time": datetime.now(timezone.utc).isoformat(),
                "primary_focus": "global_contagion"
            },
            "nodes": nodes,
            "links": links
        }

    def simulate_global_shock(
        self, 
        origin_region: str, 
        magnitude: float, 
        shock_type: str = "policy"
    ) -> Dict[str, Any]:
        """
        Simulates how a shock in one region propagates globally using the Oracle backbone.
        """
        start_node = f"market_{origin_region.lower()}"
        
        # Use existing Oracle logic but inject regional context
        # This will be refined as we integrate more granular data
        result = self._oracle.simulate_what_if(
            node_id=start_node,
            value_delta=magnitude,
            causal_graph=self._get_structural_global_links(),
            horizon_steps=3
        )
        
        return {
            "origin": origin_region,
            "shock_type": shock_type,
            "magnitude": magnitude,
            "impact_summary": result["impacts"],
            "propagation_explanation": result["explanation_summary"]
        }

    def _calculate_market_weight(self, state: GlobalMarketState) -> float:
        # Simple heuristic for alpha: stress increases weight/importance in graph
        base = 0.5
        stress = (state.geopolitical_risk_index * 0.4) + (state.fx_volatility_index * 0.6)
        return min(1.0, base + stress)

    def _get_structural_global_links(self) -> List[Dict[str, Any]]:
        # Define high-level contagion paths between major regions
        return [
            # US -> World (Rate channel)
            self._create_edge("market_us", "market_eu", 0.65, "rates"),
            self._create_edge("market_us", "market_jp", 0.55, "rates"),
            self._create_edge("market_us", "market_kr", 0.45, "rates"),
            # CN -> Asia (Supply chain channel)
            self._create_edge("market_cn", "market_kr", 0.75, "supply_chain"),
            self._create_edge("market_cn", "market_jp", 0.40, "supply_chain"),
            # EU -> US (Credit/Financial channel)
            self._create_edge("market_eu", "market_us", 0.35, "credit"),
        ]

    def _create_edge(self, source: str, target: str, strength: float, channel: str) -> Dict[str, Any]:
        return {
            "head_node": source,
            "tail_node": target,
            "relation": f"contagion_{channel}",
            "strength": strength,
            "polarity": 1.0,
            "attributes": {"channel": channel}
        }
