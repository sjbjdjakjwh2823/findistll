from app.db.client import DBClient
from app.services.distill_engine import DistillEngine
from app.services.robot_engine import RobotBrain
from app.services.types import PipelineResult
from app.services.spokes import (
    build_rag_context,
    build_training_set,
    extract_graph_triples,
)


class Orchestrator:
    def __init__(self, db: DBClient, distill: DistillEngine, robot: RobotBrain) -> None:
        self.db = db
        self.distill = distill
        self.robot = robot

    async def run(self, case_id: str, document: dict) -> PipelineResult:
        distill_result = await self.distill.extract(document)
        self.db.save_distill(case_id, distill_result)

        rag_contexts = build_rag_context(distill_result, case_id)
        if rag_contexts:
            self.db.save_rag_context(case_id, rag_contexts)

        graph_triples = extract_graph_triples(distill_result)
        if graph_triples:
            self.db.save_graph_triples(case_id, graph_triples)

        decision_result = self.robot.decide(distill_result)
        self.db.save_decision(case_id, decision_result)

        training_set = build_training_set(case_id, distill_result, decision_result)
        self.db.save_training_set(case_id, training_set)

        return PipelineResult(
            case_id=case_id,
            distill=distill_result,
            decision=decision_result
        )
