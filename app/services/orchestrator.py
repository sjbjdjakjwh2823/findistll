from app.db.client import DBClient
from app.services.distill_engine import DistillEngine
from app.services.robot_engine import RobotBrain
from app.services.types import PipelineResult


class Orchestrator:
    def __init__(self, db: DBClient, distill: DistillEngine, robot: RobotBrain) -> None:
        self.db = db
        self.distill = distill
        self.robot = robot

    async def run(self, case_id: str, document: dict) -> PipelineResult:
        distill_result = await self.distill.extract(document)
        self.db.save_distill(case_id, distill_result)

        decision_result = self.robot.decide(distill_result)
        self.db.save_decision(case_id, decision_result)

        return PipelineResult(
            case_id=case_id,
            distill=distill_result,
            decision=decision_result
        )
