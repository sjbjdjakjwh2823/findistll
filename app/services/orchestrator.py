from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.db.client import DBClient
from app.services.distill_engine import DistillEngine
from app.services.oracle import OracleEngine
from app.services.robot_engine import RobotBrain
from app.services.spokes import SpokesEngine
from app.services.agentic_brain import AgenticBrain
from app.services.audit import AuditVault
from app.services.types import PipelineResult, DistillResult, DecisionResult


class AgentMixer:
    def __init__(self, track_weights: Dict[str, float]) -> None:
        self.track_weights = {self._normalize_role(role): float(weight) for role, weight in track_weights.items()}

    def mix(self, tracks: Dict[str, str], regime_shift: Optional[str] = None) -> Dict[str, Any]:
        boosted = self._apply_regime_boost(self.track_weights, regime_shift)
        normalized = self._normalize_weights(boosted, tracks)
        ordered = sorted(normalized.items(), key=lambda item: item[1], reverse=True)
        segments = []
        for role, weight in ordered:
            content = tracks.get(role, "")
            if content:
                segments.append(f"{role.upper()}[{weight:.2f}]: {content}")
        mixed_rationale = " | ".join(segments)
        dominant_role = ordered[0][0] if ordered else ""
        return {
            "mixed_rationale": mixed_rationale,
            "weights_used": normalized,
            "weights_raw": boosted,
            "dominant_role": dominant_role,
        }

    def _apply_regime_boost(self, weights: Dict[str, float], regime_shift: Optional[str]) -> Dict[str, float]:
        adjusted = dict(weights)
        if regime_shift == "Crisis":
            for role in ("critic", "strategist"):
                adjusted[role] = adjusted.get(role, 0.0) * 1.5
        return adjusted

    def _normalize_weights(self, weights: Dict[str, float], tracks: Dict[str, str]) -> Dict[str, float]:
        available = {
            self._normalize_role(role): float(weight)
            for role, weight in weights.items()
            if weight > 0 and tracks.get(self._normalize_role(role))
        }
        total = sum(available.values())
        if total <= 0:
            return {}
        return {role: weight / total for role, weight in available.items()}

    @staticmethod
    def _normalize_role(role: str) -> str:
        return role.lower().strip()


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
        self.audit_vault = AuditVault()
        self.agentic_brain = AgenticBrain()
        self.agent_mixer = AgentMixer(
            {
                "analyst": 0.8,
                "critic": 0.5,
                "strategist": 1.0,
            }
        )
        self._current_chain_hash = "0" * 64

    async def run(self, case_id: str, document: dict) -> PipelineResult:
        # Initialize chain from DB
        history = self.db.list_audit_events(case_id)
        if history:
            self._current_chain_hash = history[-1].get("event_hash", "0" * 64)
        else:
            self._current_chain_hash = "0" * 64

        self._audit(case_id, stage="pipeline", status="started", payload={"doc_id": document.get("doc_id")})

        # 1. Distill
        distill_result = await self.distill.extract(document)
        self.db.save_distill(case_id, distill_result)
        self._audit(
            case_id,
            stage="distill",
            status="completed",
            payload={"facts_count": len(distill_result.facts)},
        )

        # 2. Spokes (Ontology)
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

        # 3. Oracle (Causality)
        regime_shift = None
        if self.oracle and edges:
            oracle_forecast = self.oracle.forecast_from_edges(edges)
            sample_node = edges[0].get("head_node")
            what_if = self.oracle.simulate_what_if(
                node_id=sample_node,
                value_delta=1.0,
                causal_graph=oracle_forecast.get("top_links", []),
                horizon_steps=3,
            )
            regime_shift = what_if.get("regime_shift")
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

        # 4. Decision (Agentic Collaboration + Mixer)
        analyst_output = await self.agentic_brain._run_analyst(distill_result)
        critique = ""
        current_analysis = analyst_output
        for _ in range(2):
            critique = await self.agentic_brain._run_critic(current_analysis, distill_result)
            if "APPROVED" in critique.upper():
                break
            current_analysis = await self.agentic_brain._refine_analysis(current_analysis, critique)

        strategist_output = await self.agentic_brain._run_strategist(current_analysis, critique)
        tracks = {
            "analyst": analyst_output,
            "critic": critique,
            "strategist": strategist_output.get("logic", ""),
        }
        mix = self.agent_mixer.mix(tracks, regime_shift=regime_shift)
        self._audit(
            case_id,
            stage="mixer",
            status="completed",
            payload={
                "regime_shift": regime_shift,
                "weights_used": mix.get("weights_used", {}),
                "dominant_role": mix.get("dominant_role", ""),
            },
        )

        decision_result = DecisionResult(
            decision=strategist_output.get("recommendation", "Review"),
            rationale=mix.get("mixed_rationale", ""),
            actions=strategist_output.get("actions", []),
            approvals=[{"role": "strategist", "status": "completed"}],
        )
        self.db.save_decision(case_id, decision_result)
        self._audit(case_id, stage="decision", status="completed", payload={"decision": decision_result.decision})
        self._audit(case_id, stage="pipeline", status="completed", payload={"case_id": case_id})

        return PipelineResult(case_id=case_id, distill=distill_result, decision=decision_result)

    def _audit(self, case_id: str, stage: str, status: str, payload: Optional[dict] = None) -> None:
        event = {
            "case_id": case_id,
            "event_type": "pipeline_stage",
            "stage": stage,
            "status": status,
            "payload": payload or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Create Chained Event
        chained = self.audit_vault.create_merkle_chain([event], prev_hash=self._current_chain_hash)[0]
        self._current_chain_hash = chained["event_hash"]
        
        self.db.save_audit_event(case_id, chained)
