from datetime import datetime, timezone
import unittest
from app.services.distill_engine import FinDistillAdapter
from app.services.oracle import OracleEngine
from app.services.spokes import SpokesEngine

class EvolutionV3Tests(unittest.TestCase):
    """
    Test suite for Preciso Evolution v3.0 (Phase 2.5 & 3.0 features)
    - Kinetic Ontology Actions
    - DML Bias Correction
    - Explainable Causal Paths
    - Competitive Precision Benchmarking
    - Cross-Source Consensus
    """

    def test_dml_bias_correction(self):
        """Pillar 2: Test DML-inspired bias reduction for broad macro terms."""
        oracle = OracleEngine()
        
        # Macro head (Inflation) vs Specific head (Product Demand)
        macro_score = oracle._score_edge({"head_node": "Inflation", "relation": "drives", "tail_node": "Bond Yield"})
        specific_score = oracle._score_edge({"head_node": "Product Demand", "relation": "drives", "tail_node": "Revenue"})
        
        self.assertIn("dml_bias_corrected", macro_score["reasoning_tags"])
        self.assertNotIn("dml_bias_corrected", specific_score["reasoning_tags"])
        # Inflation should have a penalty multiplier in the scoring logic
        print(f"DEBUG: Macro Score Strength: {macro_score['strength']}")

    def test_kinetic_action_triggering(self):
        """Pillar 1+4: Test if Oracle triggers strategic actions during simulation."""
        oracle = OracleEngine()
        causal_graph = [
            {"head_node": "inflation", "relation": "drives", "tail_node": "policy_rate", "strength": 0.9}
        ]
        
        # Triggering a shock to inflation should eventually hit policy_rate
        result = oracle.simulate_what_if("inflation", 1.0, causal_graph)
        
        self.assertIn("kinetic_actions", result)
        # policy_rate > threshold should trigger 'Refinance Corporate Debt' if impact is high
        has_refinance = any(a["action_id"] == "act:refinance_debt" for a in result["kinetic_actions"])
        self.assertTrue(has_refinance, "Kinetic Action 'Refinance Debt' should be triggered for policy_rate shock")

    def test_explainable_causal_paths(self):
        """Pillar 2: Test if simulation results include human-readable explanations."""
        oracle = OracleEngine()
        causal_graph = [
            {"head_node": "oil_price", "relation": "raises", "tail_node": "transport_cost", "strength": 0.8}
        ]
        
        result = oracle.simulate_what_if("oil_price", 1.0, causal_graph)
        
        transport_impact = next(i for i in result["impacts"] if i["node_id"] == "transport_cost")
        self.assertIn("explanation", transport_impact)
        self.assertTrue("Propagated from" in transport_impact["explanation"])
        print(f"DEBUG: Explanation: {transport_impact['explanation']}")

    def test_competitive_precision_benchmark(self):
        """Phase 1/3: Test benchmarking against Tier-1 standards (Pixel Lineage)."""
        spokes = SpokesEngine()
        
        fact_with_lineage = {"entity": "X", "metric": "Y", "value": "10", "source_anchor": {"page": 1}}
        fact_without_lineage = {"entity": "X", "metric": "Y", "value": "10"}
        
        score_high = spokes._run_precision_benchmark(fact_with_lineage, 0.5)
        score_low = spokes._run_precision_benchmark(fact_without_lineage, 0.5)
        
        self.assertGreater(score_high, score_low, "Facts without pixel lineage should be penalized in benchmark")

    def test_cross_source_consensus(self):
        """v3.0: Test if multiple sources reporting the same link increase confidence."""
        oracle = OracleEngine()
        edges = [
            {"head_node": "A", "relation": "drives", "tail_node": "B", "properties": {"confidence": "medium"}},
            {"head_node": "A", "relation": "drives", "tail_node": "B", "properties": {"confidence": "medium"}}
        ]
        
        skeleton = oracle.build_causal_skeleton(edges)
        self.assertEqual(len(skeleton), 1)
        self.assertIn("source_consensus", skeleton[0]["reasoning_tags"])
        self.assertGreater(skeleton[0]["support_count"], 1)

    def test_ontology_self_healing(self):
        """Pillar 1: Test auto-correction of inverse links (e.g., 'owned by')."""
        adapter = FinDistillAdapter()
        facts = [{"head_node": "Tesla", "relation": "is owned by", "tail_node": "Elon Musk"}]
        
        healed = adapter._self_heal_ontology_links(facts)
        self.assertEqual(healed[0]["head_node"], "Elon Musk")
        self.assertEqual(healed[0]["tail_node"], "Tesla")
        self.assertEqual(healed[0]["relation"], "owns")
        self.assertIn("ontology_healed", healed[0]["tags"])

    def test_symbolic_logic_validation(self):
        """Phase 3.5: Test arithmetic validation of accounting identities."""
        adapter = FinDistillAdapter()
        # Mismatch: 1000 != 1200 - 100
        facts = [
            {"metric": "revenue", "value": 1200},
            {"metric": "expenses", "value": 100},
            {"metric": "net income", "value": 1000}
        ]
        
        validated = adapter._validate_with_symbolic_logic(facts)
        mismatched = [f for f in validated if "symbolic_mismatch" in f.get("tags", [])]
        
        self.assertEqual(len(mismatched), 3)
        self.assertEqual(mismatched[0]["confidence"], "low")
        self.assertTrue(any("Symbolic mismatch" in issue for issue in mismatched[0]["reflection_issues"]))

    def test_agent_mixer_regime_boost(self):
        """v4.0: Test if AgentMixer correctly boosts Critic/Strategist in Crisis."""
        from app.services.orchestrator import AgentMixer
        mixer = AgentMixer({"analyst": 1.0, "critic": 1.0, "strategist": 1.0})
        
        # Normal Regime
        tracks = {"analyst": "A", "critic": "C", "strategist": "S"}
        normal_mix = mixer.mix(tracks, regime_shift=None)
        self.assertAlmostEqual(normal_mix["weights_used"]["analyst"], 0.33, places=2)
        
        # Crisis Regime
        crisis_mix = mixer.mix(tracks, regime_shift="Crisis")
        # critic and strategist should be boosted by 1.5x
        # New relative weights: analyst: 1.0, critic: 1.5, strategist: 1.5 (Total 4.0)
        # analyst: 1/4 = 0.25, critic: 1.5/4 = 0.375
        self.assertEqual(crisis_mix["weights_used"]["analyst"], 0.25)
        self.assertEqual(crisis_mix["weights_used"]["critic"], 0.375)

    def test_oracle_regime_shift_detection(self):
        """v3.7: Test if OracleEngine correctly detects High Volatility and Crisis."""
        oracle = OracleEngine()
        
        # Scenario: Moderate impacts
        impacts_low = {"A": 0.05, "B": -0.05}
        self.assertIsNone(oracle.detect_regime_shift(impacts_low))
        
        # Scenario: High Volatility (one node hit > 0.3)
        impacts_high_vol = {"A": 0.4, "B": 0.05}
        self.assertEqual(oracle.detect_regime_shift(impacts_high_vol), "High Volatility")
        
        # Scenario: Crisis (one node hit > 0.6 or total > 1.5)
        impacts_crisis = {"A": 0.7, "B": 0.5, "C": 0.5}
        self.assertEqual(oracle.detect_regime_shift(impacts_crisis), "Crisis")

    def test_dynamic_weight_learning(self):
        """Pillar 3.8: Test if Oracle learns higher weights for recent data."""
        oracle = OracleEngine()
        now_iso = datetime.now(timezone.utc).isoformat()
        old_iso = "2020-01-01T00:00:00+00:00"
        
        edges = [
            {"head_node": "A", "relation": "drives", "tail_node": "B", "event_time": now_iso},
            {"head_node": "C", "relation": "drives", "tail_node": "D", "event_time": old_iso}
        ]
        
        weights = oracle._learn_dynamic_weights(edges)
        self.assertGreater(weights[("a", "b")], weights[("c", "d")])

    def test_fed_feed_real_time_override(self):
        """Phase 4.5: Fed shock should consume real-time feed deltas."""
        oracle = OracleEngine()
        oracle.update_fed_snapshot({"dot_plot_change": 0.5}, observed_at=datetime.now(timezone.utc))
        result = oracle.simulate_what_if("fed_dot_plot", 0.0, causal_graph=[], horizon_steps=1)
        impact_map = {row["node_id"]: row["delta"] for row in result["impacts"]}
        self.assertIn("tech_valuation", impact_map)
        self.assertLess(impact_map["tech_valuation"], 0.0)

    def test_contagion_velocity_amplifies_under_stress(self):
        """Phase 4.5: Contagion velocity should rise with stress signals."""
        oracle = OracleEngine()
        base = oracle._calculate_contagion_velocity(
            None,
            "day",
            shock_magnitude=0.05,
            volatility=0.0,
            connectivity=0.0,
            liquidity_stress=0.0,
        )
        stressed = oracle._calculate_contagion_velocity(
            "Crisis",
            "day",
            shock_magnitude=0.6,
            volatility=0.05,
            connectivity=3.0,
            liquidity_stress=0.8,
        )
        self.assertGreater(stressed, base)

if __name__ == "__main__":
    unittest.main()
