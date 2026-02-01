import os
import asyncio
import unittest
from app.db.client import InMemoryDB
from app.services.distill_engine import FinDistillAdapter
from app.services.robot_engine import FinRobotAdapter
from app.services.orchestrator import Orchestrator


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


if __name__ == "__main__":
    unittest.main()
