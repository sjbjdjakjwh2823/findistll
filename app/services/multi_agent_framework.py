from __future__ import annotations

import time
from typing import Any, Dict, Optional

from app.services.distill_engine import DistillEngine
from app.services.robot_engine import RobotBrain
from app.services.selfcheck import SelfCheckService
from app.services.retrieval_trust import AuditEventLogger, HybridRetriever, StructuredChunker
from app.services.types import DistillResult, DecisionResult
from app.db.client import DBClient


class MultiAgentOrchestrator:
    """
    Financial-grade multi-agent collaboration pipeline.
    Investigator -> Analyst -> Auditor -> Manager.
    """

    def __init__(self, db: DBClient, distill: DistillEngine, robot: RobotBrain) -> None:
        self.db = db
        self.distill = distill
        self.robot = robot
        self.audit = AuditEventLogger()
        self.chunker = StructuredChunker()
        self.selfcheck = SelfCheckService()

    async def run(self, case_id: str, document: dict) -> Dict[str, Any]:
        # Step 1: Investigator (facts only)
        distill_result = await self.distill.extract(document)
        self.db.save_distill(case_id, distill_result)
        case_row = self.db.get_case(case_id) or {}
        case_uuid = case_row.get("id") or case_id
        self.audit.log("FACT_EXTRACTION_COMPLETED", case_id=str(case_uuid))

        # Step 2: Analyst (analysis draft)
        decision_result = await self.robot.decide(distill_result)
        analysis_draft = self._build_analysis_draft(distill_result, decision_result)
        self.db.save_decision(case_id, decision_result)
        self.audit.log("ANALYSIS_DRAFT_CREATED", case_id=str(case_uuid))

        # Step 3: Auditor (self-check + retrieval)
        auditor_report = self._run_auditor(distill_result, decision_result)
        self.audit.log("SELF_CHECK_COMPLETED", case_id=str(case_uuid))

        # Step 4: Manager (compose final + gating)
        manager = self._compose_manager_decision(decision_result, auditor_report)
        self.audit.log("FINAL_DECISION_COMPOSED", case_id=str(case_uuid))

        fields = {
            "analysis_draft": analysis_draft,
            "auditor_report": auditor_report,
            "manager_decision": manager,
            "confidence_score": manager.get("confidence_score"),
            "needs_review": manager.get("needs_review"),
        }
        if manager.get("needs_review"):
            self.db.update_case_status(case_id, "needs_review", fields)
        else:
            self.db.update_case_status(case_id, "ready_for_approval", fields)

        return {
            "case_id": case_id,
            "analysis_draft": analysis_draft,
            "auditor_report": auditor_report,
            "manager_decision": manager,
        }

    def _build_analysis_draft(self, distill: DistillResult, decision: DecisionResult) -> str:
        facts = distill.facts or []
        cot = distill.cot_markdown or ""
        rationale = decision.rationale or ""
        lines = [
            "# 분석 초안",
            "## 요약",
            rationale,
            "",
            "## Facts",
            "\n".join([f"- {self._stringify_fact(f)}" for f in facts[:20]]),
        ]
        if cot:
            lines.extend(["", "## CoT", cot])
        return "\n".join(lines).strip()

    def _run_auditor(self, distill: DistillResult, decision: DecisionResult) -> Dict[str, Any]:
        check = self.selfcheck.evaluate(decision, distill)
        confidence_score = float(check.get("confidence_score", 0.0))
        issues = []
        if confidence_score < 0.7:
            issues.append("low_consistency_score")

        retriever = HybridRetriever()
        similar = retriever.search(
            query_text=decision.rationale or "risk analysis",
            filters={"approval_status": "approved"},
            top_k=5,
            use_graph_expansion=True,
        )
        if not similar.get("results"):
            issues.append("no_similar_cases_found")

        return {
            "issues_found": issues,
            "risk_flags": issues,
            "confidence_score": round(confidence_score, 3),
            "similar_case_count": len(similar.get("results") or []),
            "selfcheck": check,
        }

    def _compose_manager_decision(self, decision: DecisionResult, auditor_report: Dict[str, Any]) -> Dict[str, Any]:
        confidence = float(auditor_report.get("confidence_score", 0.0))
        status = "Ready for Approval"
        needs_review = False
        if confidence < 0.7:
            status = "Needs Human Review"
            needs_review = True
        elif confidence < 0.85:
            status = "Review Recommended"
        return {
            "decision": decision.decision,
            "rationale": decision.rationale,
            "status": status,
            "confidence_score": round(confidence, 3),
            "needs_review": needs_review,
        }

    def _stringify_fact(self, fact: Any) -> str:
        if isinstance(fact, dict):
            key = fact.get("concept") or fact.get("key") or fact.get("label") or "fact"
            value = fact.get("value") or fact.get("text") or fact
            return f"{key}: {value}"
        return str(fact)
