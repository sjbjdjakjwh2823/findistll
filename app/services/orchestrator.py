import logging
from typing import Dict

from app.db.client import DBClient
from app.services.distill_engine import DistillEngine
from app.services.robot_engine import RobotBrain
from app.services.types import PipelineResult
from app.services.spokes import (
    build_rag_context,
    build_training_set,
    extract_graph_triples,
)
from app.services.spoke_d_enrichment import build_causal_triples_from_training_set

logger = logging.getLogger(__name__)

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

        decision_result = await self.robot.decide(distill_result)
        self.db.save_decision(case_id, decision_result)

        training_set = build_training_set(case_id, distill_result, decision_result)
        self.db.save_training_set(case_id, training_set)

        # Spoke D enrichment: materialize causal candidates as explicit triples.
        # This improves on-prem graph reasoning and makes the causal layer queryable.
        causal_triples = build_causal_triples_from_training_set(training_set)
        if causal_triples:
            self.db.save_graph_triples(case_id, causal_triples)

        # Supabase-only: autofill OpsGraph so kg_relationships (3-hop) is actually useful.
        # Kept behind a feature flag to avoid overhead for local/dev users.
        try:
            import os
            if os.getenv("OPSGRAPH_AUTOFILL_ENABLED", "0") == "1":
                from app.core.config import load_settings
                from app.core.tenant_context import get_effective_tenant_id
                from app.db.tenant_scoped_client import create_tenant_aware_client
                from app.services.opsgraph_autofill import autofill_opsgraph
                settings = load_settings()
                if settings.supabase_url and settings.supabase_service_role_key:
                    tenant_id = get_effective_tenant_id() or settings.default_tenant_id
                    client = create_tenant_aware_client(
                        settings.supabase_url,
                        settings.supabase_service_role_key,
                        default_tenant_id=tenant_id,
                    )
                    company = (distill_result.metadata or {}).get("company") or (distill_result.metadata or {}).get("entity") or "Unknown"
                    title = (distill_result.metadata or {}).get("title") or company
                    counts = autofill_opsgraph(
                        client=client,
                        tenant_id=tenant_id,
                        case_id=case_id,
                        title=title,
                        company=str(company),
                        facts=(distill_result.facts or []),
                        graph_triples=(graph_triples or []),
                    )
                    # Build kg_relationships from ops_* (includes ops_relationships mapping).
                    try:
                        from app.services.knowledge_graph import KnowledgeGraphBuilder
                        KnowledgeGraphBuilder(client).build()
                    except Exception as exc:
                        logger.warning("knowledge graph build failed", exc_info=exc)
                    # Best-effort observability: store in audit logs if DB supports it.
                    try:
                        self.db.append_audit_log(
                            {
                                "action": "opsgraph_autofill",
                                "actor_type": "system",
                                "actor_id": "orchestrator",
                                "context": {"case_id": case_id},
                                "outcome": counts,
                            }
                        )
                    except Exception as exc:
                        logger.warning("opsgraph audit logging failed", exc_info=exc)
        except Exception as exc:
            logger.warning("opsgraph autofill failed", exc_info=exc)

        return PipelineResult(
            case_id=case_id,
            distill=distill_result,
            decision=decision_result
        )

    @staticmethod
    def task_map() -> Dict[str, str]:
        """
        Sync/async map for orchestration visibility.
        """
        return {
            "distill_extract": "sync",
            "rag_context_build": "sync",
            "graph_triples": "sync",
            "decision": "sync",
            "training_set": "async",
            "data_quality_prune": "async",
        }
