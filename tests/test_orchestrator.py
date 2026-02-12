import os
import asyncio
import unittest
from app.db.client import InMemoryDB
from app.services.distill_engine import FinDistillAdapter
from app.services.robot_engine import FinRobotAdapter
from app.services.orchestrator import Orchestrator
from app.services.spokes import build_training_set
from app.services.types import DistillResult, DecisionResult


class OrchestratorTests(unittest.TestCase):
    def test_pipeline_run(self):
        os.environ["DISTILL_OFFLINE"] = "1"
        db = InMemoryDB()
        distill = FinDistillAdapter()
        robot = FinRobotAdapter()
        orch = Orchestrator(db, distill, robot)

        case_id = db.create_case({"title": "Test Case"})
        db.add_document(case_id, {"doc_id": "doc_1", "content": "Test", "mime_type": "text/plain"})

        result = asyncio.run(orch.run(case_id, db.docs["doc_1"]))
        self.assertEqual(result.case_id, case_id)
        self.assertEqual(result.decision.decision, "Review")
        self.assertGreaterEqual(len(db.list_rag_context()), 1)
        self.assertEqual(len(db.list_training_sets()), 1)
        training_set = db.list_training_sets()[0]
        self.assertIn("ontology", training_set)
        self.assertIn("predictive_signals", training_set)
        self.assertIn("evidence_paths", training_set)
        self.assertIn("training_prompt", training_set)
        self.assertIn("output_narrative", training_set)

    def test_training_set_causal_fields(self):
        facts = [
            {"entity": "Acme Corp", "metric": "Revenue", "period": "2023-Q1", "value": 100},
            {"entity": "Acme Corp", "metric": "Revenue", "period": "2023-Q2", "value": 120},
            {"entity": "Acme Corp", "metric": "Revenue", "period": "2023-Q3", "value": 140},
            {"entity": "Acme Corp", "metric": "Revenue", "period": "2023-Q4", "value": 160},
            {"entity": "Acme Corp", "metric": "Profit", "period": "2023-Q1", "value": 8},
            {"entity": "Acme Corp", "metric": "Profit", "period": "2023-Q2", "value": 10},
            {"entity": "Acme Corp", "metric": "Profit", "period": "2023-Q3", "value": 12},
            {"entity": "Acme Corp", "metric": "Profit", "period": "2023-Q4", "value": 14},
        ]
        distill = DistillResult(
            facts=facts,
            cot_markdown="Revenue growth supports profit expansion.",
            metadata={"source": "unit_test"},
        )
        decision = DecisionResult(decision="Review", rationale="Revenue appears to affect profit.")
        training_set = build_training_set("case_test", distill, decision)
        self.assertIn("predictive_signals", training_set)
        self.assertGreaterEqual(len(training_set["predictive_signals"]["causal_candidates"]), 1)
        self.assertGreaterEqual(len(training_set["evidence_paths"]), 1)
        self.assertGreaterEqual(len(training_set["ontology"]["nodes"]), 1)
        self.assertGreaterEqual(len(training_set["ontology"]["edges"]), 1)
        for field in ["training_prompt", "output_narrative"]:
            self.assertTrue(all(ord(ch) < 128 or ch in "\n\t" for ch in training_set[field]))


if __name__ == "__main__":
    unittest.main()
