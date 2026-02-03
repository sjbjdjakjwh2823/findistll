import asyncio
import os
import unittest

from app.db.client import InMemoryDB
from app.services.distill_engine import FinDistillAdapter
from app.services.oracle import OracleEngine
from app.services.orchestrator import Orchestrator
from app.services.robot_engine import FinRobotAdapter
from app.services.spokes import SpokesEngine


class OrchestratorTests(unittest.TestCase):
    def test_pipeline_run(self):
        os.environ["DISTILL_OFFLINE"] = "1"
        db = InMemoryDB()
        distill = FinDistillAdapter()
        robot = FinRobotAdapter()
        oracle = OracleEngine()
        orch = Orchestrator(db, distill, robot, oracle=oracle)

        case_id = db.create_case({"title": "Test Case"})
        db.add_document(case_id, {"doc_id": "doc_1", "content": "Test", "mime_type": "text/plain"})

        result = asyncio.run(orch.run(case_id, db.docs["doc_1"]))
        self.assertEqual(result.case_id, case_id)
        self.assertEqual(result.decision.decision, "Maintain / Overweight")
        self.assertTrue("oracle" not in result.distill.metadata)

        audit_events = db.list_audit_events(case_id)
        self.assertGreaterEqual(len(audit_events), 4)
        self.assertEqual(audit_events[0]["stage"], "pipeline")

    def test_pipeline_with_spokes_and_oracle_metadata(self):
        os.environ["DISTILL_OFFLINE"] = "1"
        db = InMemoryDB()
        distill = FinDistillAdapter()
        robot = FinRobotAdapter()
        oracle = OracleEngine()
        spokes = SpokesEngine()
        orch = Orchestrator(db, distill, robot, spokes=spokes, oracle=oracle)

        case_id = db.create_case({"title": "Graph Case"})
        db.add_document(
            case_id,
            {
                "doc_id": "doc_2",
                "content": "ACME revenue 1000 in 2024-Q2",
                "mime_type": "text/plain",
            },
        )
        # Inject one explicit fact so Spokes and Oracle paths are exercised.
        db.docs["doc_2"]["content"] = ""
        db.docs["doc_2"]["facts"] = [{"entity": "ACME", "metric": "revenue", "value": "1000", "period": "2024-Q2"}]

        # Monkey-patch distill extraction output for deterministic test behavior.
        async def fake_extract(_document):
            from app.services.types import DistillResult

            return DistillResult(
                facts=db.docs["doc_2"]["facts"],
                cot_markdown="",
                metadata={"self_reflection": {"rounds_executed": 1, "input_count": 1, "output_count": 1, "history": []}},
            )

        distill.extract = fake_extract

        result = asyncio.run(orch.run(case_id, db.docs["doc_2"]))
        self.assertIn("oracle", result.distill.metadata)
        self.assertGreaterEqual(result.distill.metadata["oracle"]["forecast"]["link_count"], 1)


if __name__ == "__main__":
    unittest.main()
