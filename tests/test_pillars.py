from datetime import datetime, timezone
import unittest

from app.services.distill_engine import FinDistillAdapter
from app.services.spokes import SpokesEngine


class PillarTests(unittest.TestCase):
    def test_self_reflection_repairs_and_dedupes_facts(self):
        adapter = FinDistillAdapter()
        reflected, summary = adapter._self_reflect_facts(
            [
                {"entity": "ACME", "metric": "revenue", "value": "1,000", "period": "2024"},
                {"entity": "ACME", "metric": "revenue", "value": "1,000", "period": "2024"},
                "Operating margin improved",
            ],
            max_rounds=2,
        )

        self.assertEqual(summary["enabled"], True)
        self.assertEqual(summary["input_count"], 3)
        self.assertEqual(len(reflected), 2)
        numeric_fact = next(f for f in reflected if f.get("metric") == "revenue")
        self.assertEqual(numeric_fact.get("confidence"), "medium")

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
        )

        self.assertEqual(len(edges), 2)
        self.assertTrue(edges[0].get("event_time"))
        self.assertEqual(edges[0].get("time_granularity"), "quarter")

        as_of = datetime(2024, 6, 15, tzinfo=timezone.utc)
        visible = spokes.gate_edges_as_of(edges, as_of=as_of)
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["tail_node"], "1000")


if __name__ == "__main__":
    unittest.main()
