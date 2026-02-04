import unittest
from datetime import datetime, timezone
from app.services.global_engine import GlobalInterconnectednessEngine

class TestGlobalEngine(unittest.TestCase):
    def setUp(self):
        self.engine = GlobalInterconnectednessEngine()

    def test_regional_update(self):
        self.engine.update_regional_state("US", rate=5.25, gpr=0.1)
        graph = self.engine.get_global_contagion_graph()
        us_node = next(n for n in graph["nodes"] if n["region"] == "US")
        self.assertEqual(us_node["attributes"]["rate"], 5.25)
        self.assertEqual(us_node["attributes"]["gpr"], 0.1)

    def test_global_shock_simulation(self):
        # Shock in US should propagate to EU based on structural links
        result = self.engine.simulate_global_shock("US", magnitude=0.5)
        impact_nodes = [row["node_id"] for row in result["impact_summary"]]
        self.assertIn("market_eu", impact_nodes)
        self.assertIn("market_jp", impact_nodes)
        
        # Verify impact magnitude is positive (propagated delta)
        eu_impact = next(row["delta"] for row in result["impact_summary"] if row["node_id"] == "market_eu")
        self.assertGreater(eu_impact, 0)

    def test_market_weight_stress(self):
        # Increase stress in KR
        self.engine.update_regional_state("KR", fxv=0.8)
        graph = self.engine.get_global_contagion_graph()
        kr_node = next(n for n in graph["nodes"] if n["region"] == "KR")
        self.assertGreater(kr_node["weight"], 0.5)

if __name__ == "__main__":
    unittest.main()
