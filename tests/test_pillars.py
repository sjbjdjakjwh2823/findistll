from datetime import datetime, timezone
import unittest

from app.services.distill_engine import FinDistillAdapter
from app.services.oracle import OracleEngine
from app.services.spokes import SpokesEngine


class PillarTests(unittest.TestCase):
    def test_self_reflection_repairs_and_dedupes_facts(self):
        adapter = FinDistillAdapter()
        reflected, summary = adapter._self_reflect_facts(
            [
                {"entity": "ACME", "metric": "revenue", "value": "1,000", "period": "2024"},
                {"entity": "ACME", "metric": "revenue decrease", "value": "12", "period": "2024-Q2"},
                {"entity": "ACME", "metric": "revenue", "value": "1,000", "period": "2024"},
                "Operating margin improved",
            ],
            max_rounds=2,
        )

        self.assertEqual(summary["enabled"], True)
        self.assertEqual(summary["input_count"], 4)
        self.assertEqual(len(reflected), 3)
        self.assertIn("relation_inversion", summary["error_types_detected"])
        numeric_fact = next(f for f in reflected if f.get("metric") == "revenue")
        self.assertEqual(numeric_fact.get("confidence"), "medium")
        inverted_fact = next(f for f in reflected if f.get("metric") == "revenue decrease")
        self.assertLess(float(inverted_fact.get("value")), 0)

    def test_temporal_edge_build_and_gate(self):
        spokes = SpokesEngine()
        edges = spokes.build_graph_edges(
            case_id="case_1",
            facts=[
                {
                    "entity": "ACME",
                    "metric": "reported_revenue",
                    "value": "1000",
                    "period": "2024-Q2",
                },
                {
                    "entity": "ACME",
                    "metric": "reported_revenue",
                    "value": "900",
                    "valid_from": "2020-01-01",
                    "valid_to": "2020-12-31",
                },
            ],
            document={"doc_id": "doc_1"},
            self_reflection={"rounds_executed": 2, "input_count": 2, "output_count": 2, "history": [{"issues_found": 1}]},
        )

        self.assertEqual(len(edges), 2)
        self.assertTrue(edges[0].get("event_time"))
        self.assertEqual(edges[0].get("time_granularity"), "quarter")
        self.assertIn("reflection_quality", edges[0]["properties"])
        self.assertIn("temporal_quality", edges[0]["properties"])
        self.assertIn("edge_weight", edges[0]["properties"])

        as_of = datetime(2024, 6, 15, tzinfo=timezone.utc)
        visible = spokes.gate_edges_as_of(edges, as_of=as_of)
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["tail_node"], "1000")

    def test_oracle_what_if_simulation(self):
        oracle = OracleEngine()
        causal_graph = [
            {"head_node": "revenue", "relation": "drives", "tail_node": "margin", "strength": 0.8, "time_granularity": "quarter"},
            {"head_node": "margin", "relation": "drives", "tail_node": "valuation", "strength": 0.6, "time_granularity": "quarter"},
        ]
        result = oracle.simulate_what_if("revenue", 1.0, causal_graph, horizon_steps=2)

        self.assertEqual(result["node_id"], "revenue")
        self.assertGreaterEqual(len(result["impacts"]), 2)
        impacted_nodes = {row["node_id"] for row in result["impacts"]}
        self.assertIn("valuation", impacted_nodes)

    def test_oracle_matrix_boost_and_root_cause_path(self):
        oracle = OracleEngine()
        causal_graph = oracle.build_causal_skeleton(
            [
                {
                    "head_node": "Inflation",
                    "relation": "drives",
                    "tail_node": "Interest Rate",
                    "time_granularity": "month",
                    "properties": {"confidence": "high", "reflection_quality": 0.9, "temporal_quality": 0.8},
                },
                {
                    "head_node": "Interest Rate",
                    "relation": "drives",
                    "tail_node": "Tech Valuation",
                    "time_granularity": "month",
                    "properties": {"confidence": "high", "reflection_quality": 0.9, "temporal_quality": 0.8},
                },
            ]
        )

        self.assertEqual(len(causal_graph), 2)
        first_edge = causal_graph[0]
        self.assertGreater(first_edge.get("matrix_boost", 1.0), 1.0)
        self.assertTrue(first_edge.get("reasoning_tags"))

        what_if = oracle.simulate_what_if("Inflation", 1.0, causal_graph, horizon_steps=3)
        impact_map = {row["node_id"]: row["delta"] for row in what_if["impacts"]}
        self.assertIn("Tech Valuation", impact_map)
        self.assertLess(impact_map["Tech Valuation"], 0)

        root = oracle.get_root_cause_path("Tech Valuation", causal_graph, max_depth=4)
        self.assertEqual(root["target_node"], "Tech Valuation")
        self.assertEqual(root["root_cause"], "Inflation")
        self.assertEqual(root["path"], ["Inflation", "Interest Rate", "Tech Valuation"])
        self.assertGreater(root["influence_score"], 0)
        self.assertLess(root["directional_effect"], 0)
        self.assertIn("confidence_interval", root)
        self.assertIn("data_lineage", root)
        self.assertGreaterEqual(root["confidence_interval"]["upper"], root["confidence_interval"]["lower"])


if __name__ == "__main__":
    unittest.main()
