from typing import Optional

from app.db.client import DBClient
from app.services.distill_engine import DistillEngine
from app.services.robot_engine import RobotBrain
from app.services.spokes import SpokesEngine
from app.services.types import PipelineResult


class Orchestrator:
    def __init__(
        self,
        db: DBClient,
        distill: DistillEngine,
        robot: RobotBrain,
        spokes: Optional[SpokesEngine] = None,
    ) -> None:
        self.db = db
        self.distill = distill
        self.robot = robot
        self.spokes = spokes

    async def run(self, case_id: str, document: dict) -> PipelineResult:
        distill_result = await self.distill.extract(document)
        self.db.save_distill(case_id, distill_result)

        if self.spokes:
            edges = self.spokes.build_graph_edges(case_id=case_id, facts=distill_result.facts, document=document)
            self.db.upsert_graph_edges(case_id, edges)
            distill_result.metadata["graph_edges_generated"] = len(edges)

        decision_result = self.robot.decide(distill_result)
        self.db.save_decision(case_id, decision_result)

        return PipelineResult(case_id=case_id, distill=distill_result, decision=decision_result)
