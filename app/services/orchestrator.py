from datetime import datetime, timezone
from typing import Optional

from app.db.client import DBClient
from app.services.distill_engine import DistillEngine
from app.services.oracle import OracleEngine
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
        oracle: Optional[OracleEngine] = None,
    ) -> None:
        self.db = db
        self.distill = distill
        self.robot = robot
        self.spokes = spokes
        self.oracle = oracle

    async def run(self, case_id: str, document: dict) -> PipelineResult:
        self._audit(case_id, stage="pipeline", status="started", payload={"doc_id": document.get("doc_id")})

        distill_result = await self.distill.extract(document)
        self.db.save_distill(case_id, distill_result)
        self._audit(
            case_id,
            stage="distill",
            status="completed",
            payload={"facts_count": len(distill_result.facts)},
        )

        edges = []
        if self.spokes:
            edges = self.spokes.build_graph_edges(
                case_id=case_id,
                facts=distill_result.facts,
                document=document,
                self_reflection=distill_result.metadata.get("self_reflection"),
            )
            self.db.upsert_graph_edges(case_id, edges)
            distill_result.metadata["graph_edges_generated"] = len(edges)
            self._audit(
                case_id,
                stage="spokes",
                status="completed",
                payload={"graph_edges_generated": len(edges)},
            )

        if self.oracle and edges:
            oracle_forecast = self.oracle.forecast_from_edges(edges)
            sample_node = edges[0].get("head_node")
            what_if = self.oracle.simulate_what_if(
                node_id=sample_node,
                value_delta=1.0,
                causal_graph=oracle_forecast.get("top_links", []),
                horizon_steps=3,
            )
            distill_result.metadata["oracle"] = {"forecast": oracle_forecast, "sample_what_if": what_if}
            self._audit(
                case_id,
                stage="oracle",
                status="completed",
                payload={"causal_links": oracle_forecast.get("link_count", 0), "seed_node": sample_node},
            )
        elif self.oracle:
            self._audit(
                case_id,
                stage="oracle",
                status="skipped",
                payload={"reason": "no_graph_edges"},
            )

        decision_result = self.robot.decide(distill_result)
        self.db.save_decision(case_id, decision_result)
        self._audit(case_id, stage="decision", status="completed", payload={"decision": decision_result.decision})
        self._audit(case_id, stage="pipeline", status="completed", payload={"case_id": case_id})

        return PipelineResult(case_id=case_id, distill=distill_result, decision=decision_result)

    def _audit(self, case_id: str, stage: str, status: str, payload: Optional[dict] = None) -> None:
        event = {
            "event_type": "pipeline_stage",
            "stage": stage,
            "status": status,
            "payload": payload or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.db.save_audit_event(case_id, event)
