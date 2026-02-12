"""
Robot Engine - Decision-Making Core
Phase 2 Integration: RAG + Causal Reasoning
"""

import os
import sys
import logging
import time
from typing import Any, Dict, Optional, List
from app.services.types import DecisionResult, DistillResult
from app.services.feature_flags import get_flag
from app.services.case_embedding_search import CaseEmbeddingSearch

logger = logging.getLogger(__name__)


class RobotBrain:
    async def decide(self, distill: DistillResult) -> DecisionResult:
        raise NotImplementedError


class FinRobotAdapter(RobotBrain):
    """
    Adapter that routes decisions to FinRobot when enabled.
    
    Phase 2 Enhancement:
    - Integrates RAG Engine (Spoke C) for evidence retrieval
    - Integrates Causal Engine (Spoke D) for counterfactual analysis
    - Adds trace field for transparency/auditability
    """
    
    def __init__(self):
        self._rag_engine = None
        self._causal_engine = None
        self._supabase_client = None
    
    def _get_supabase_client(self):
        """Lazy-load Supabase client."""
        if self._supabase_client is None:
            try:
                from app.core.config import load_settings
                from app.db.tenant_scoped_client import create_tenant_aware_client
                url = os.getenv("SUPABASE_URL", "https://nnuixqxmalttautcqckt.supabase.co")
                key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
                if url and key:
                    settings = load_settings()
                    self._supabase_client = create_tenant_aware_client(
                        url,
                        key,
                        default_tenant_id=settings.default_tenant_id,
                    )
            except Exception as e:
                logger.warning(f"Failed to init Supabase: {e}")
        return self._supabase_client

    def _get_db(self):
        try:
            from app.db.registry import get_db
            return get_db()
        except Exception:
            return None
    
    def _get_rag_engine(self):
        """Lazy-load RAG Engine (Spoke C)."""
        if self._rag_engine is None:
            try:
                from app.services.spoke_c_rag import RAGEngine
                self._rag_engine = RAGEngine(
                    supabase_client=self._get_supabase_client(),
                    openai_api_key=os.getenv("OPENAI_API_KEY"),
                )
            except Exception as e:
                logger.warning(f"Failed to init RAG Engine: {e}")
        return self._rag_engine
    
    def _get_causal_engine(self):
        """Lazy-load Causal Engine (Spoke D)."""
        if self._causal_engine is None:
            try:
                from app.services.spoke_d_causal import CausalEngine
                self._causal_engine = CausalEngine(
                    supabase_client=self._get_supabase_client()
                )
                self._causal_engine.build_graph()
            except Exception as e:
                logger.warning(f"Failed to init Causal Engine: {e}")
        return self._causal_engine
    
    async def decide(self, distill: DistillResult) -> DecisionResult:
        start_time = time.time()
        trace = {
            "rag_context": None,
            "causal_analysis": None,
            "oracle_insight": None,
            "selfcheck": None,
            "latency_ms": 0,
        }
        
        if not get_flag("finrobot_enabled"):
            result = self._fallback(distill)
            # Still try to enrich with Phase 2 engines
            try:
                result = await self._enrich_with_ai_brain(distill, result, trace)
            except Exception as e:
                logger.warning(f"AI Brain enrichment failed: {e}")
            trace["latency_ms"] = int((time.time() - start_time) * 1000)
            self._attach_selfcheck(distill, result, trace)
            result.trace = trace
            self._save_ai_brain_trace(distill.metadata.get("case_id", ""), trace, result.decision)
            self._log_rag_faithfulness(result, trace)
            return result

        vendor_root = os.path.join(os.getcwd(), "vendor")
        if vendor_root not in sys.path:
            sys.path.append(vendor_root)

        try:
            import autogen
            from finrobot.agents.workflow import SingleAssistant
            from finrobot.utils import register_keys_from_json
        except Exception as exc:
            return DecisionResult(
                decision="Review",
                rationale=f"FinRobot import failed: {exc}",
                actions=[{"type": "request_more_info", "priority": "medium"}],
                approvals=[{"role": "analyst", "required": True}],
                trace=trace,
            )

        config_path = os.getenv("FINROBOT_OAI_CONFIG", "OAI_CONFIG_LIST")
        api_keys_path = os.getenv("FINROBOT_API_KEYS", "config_api_keys")
        if os.path.exists(api_keys_path):
            register_keys_from_json(api_keys_path)

        llm_config = {
            "config_list": autogen.config_list_from_json(
                config_path,
                filter_dict={"model": [os.getenv("FINROBOT_MODEL", "gpt-4-0125-preview")]},
            ),
            "timeout": 120,
            "temperature": 0.2,
        }

        message = await self._build_message_with_ai_brain(distill, trace)

        try:
            assistant = SingleAssistant(
                "Market_Analyst",
                llm_config,
                human_input_mode="NEVER",
                max_consecutive_auto_reply=6,
            )
            assistant.chat(message)
        except Exception as exc:
            return DecisionResult(
                decision="Review",
                rationale=f"FinRobot execution failed: {exc}",
                actions=[{"type": "request_more_info", "priority": "medium"}],
                approvals=[{"role": "analyst", "required": True}],
                trace=trace,
            )

        trace["latency_ms"] = int((time.time() - start_time) * 1000)
        self._save_ai_brain_trace(distill.metadata.get("case_id", ""), trace, "Review")
        result = DecisionResult(
            decision="Review",
            rationale="FinRobot chat executed with AI Brain context. Review agent output logs.",
            actions=[{"type": "review_agent_output", "priority": "high"}],
            approvals=[{"role": "analyst", "required": True}],
            trace=trace,
        )
        self._attach_selfcheck(distill, result, trace)
        self._log_rag_faithfulness(result, trace)
        return result
    

    def _save_ai_brain_trace(self, case_id: str, trace: Dict[str, Any], decision: str) -> None:
        try:
            client = self._get_supabase_client()
            if not client:
                return
            client.table("ai_brain_traces").insert({
                "case_id": case_id,
                "query": trace.get("query"),
                "rag_results": trace.get("rag_context"),
                "causal_results": trace.get("causal_analysis"),
                "final_decision": {"decision": decision},
                "latency_ms": trace.get("latency_ms"),
                "model_used": os.getenv("FINROBOT_MODEL", "gpt-4"),
            }).execute()
        except Exception as exc:
            logger.warning(f"Failed to save ai_brain_trace: {exc}")

    async def _build_message_with_ai_brain(
        self,
        distill: DistillResult,
        trace: Dict[str, Any],
    ) -> str:
        """Build message with RAG and Causal context injected."""
        # Base message
        facts = distill.facts[:20]
        facts_lines = "\n".join([f"- {f}" for f in facts])
        cot = distill.cot_markdown[:2000]
        
        message_parts = [
            "You are FinRobot. Use the extracted facts, CoT, and evidence below to produce a decision summary.",
            "",
            "Facts (sample):",
            facts_lines,
            "",
            "CoT (excerpt):",
            cot,
        ]
        
        # Phase 2: RAG Context (Spoke C)
        rag_context = await self._get_rag_context(distill, trace)
        if rag_context:
            message_parts.extend([
                "",
                "--- EVIDENCE FROM KNOWLEDGE BASE ---",
                rag_context,
            ])
        
        # Phase 2: Causal Analysis (Spoke D)
        causal_context = await self._get_causal_context(distill, trace)
        if causal_context:
            message_parts.extend([
                "",
                "--- CAUSAL ANALYSIS ---",
                causal_context,
            ])

        # Evidence-grounded causal story chain (macro -> fundamentals -> supply chain -> market)
        causal_story = await self._get_causal_story_context(distill, trace)
        if causal_story:
            message_parts.extend([
                "",
                "--- CAUSAL STORY (EVIDENCE-GROUNDED) ---",
                causal_story,
            ])

        # Graph Reasoning (3-hop)
        graph_context = await self._get_graph_context(distill, trace)
        if graph_context:
            message_parts.extend([
                "",
                "--- GRAPH PATHS (3-HOP) ---",
                graph_context,
            ])
        
        # v17.5: Oracle Analysis
        oracle_context = await self._get_oracle_context(distill, trace)
        if oracle_context:
            message_parts.extend([
                "",
                "[Real-time Oracle Insight]",
                oracle_context,
            ])
        
        message_parts.append("")
        message_parts.append("Return a concise decision with risks and recommended actions.")
        
        return "\n".join(message_parts)

    async def _get_causal_story_context(
        self,
        distill: DistillResult,
        trace: Dict[str, Any],
    ) -> Optional[str]:
        try:
            if os.getenv("CAUSAL_STORY_ENABLED", "1") != "1":
                return None
            db = self._get_db()
            if not db:
                return None
            from app.services.causal_story import CausalStoryService

            service = CausalStoryService(db=db)
            story = await service.build_story(distill=distill)
            trace["causal_story"] = {
                "status": story.get("status"),
                "as_of": story.get("as_of"),
                "steps_count": len(story.get("steps") or []),
            }
            if story.get("status") != "ok":
                return None
            lines: List[str] = []
            for idx, step in enumerate(story.get("steps") or [], 1):
                claim = step.get("claim")
                cat = step.get("category")
                st = step.get("step_type")
                conf = step.get("confidence")
                if claim:
                    lines.append(f"{idx}. [{cat}/{st}] {claim} (conf={conf})")
            return "\n".join(lines).strip() if lines else None
        except Exception as exc:
            trace["causal_story"] = {"error": str(exc)}
            return None

    async def _get_rag_context(
        self,
        distill: DistillResult,
        trace: Dict[str, Any],
    ) -> Optional[str]:
        """Retrieve relevant context from RAG Engine."""
        rag = self._get_rag_engine()
        client = self._get_supabase_client()
        db = self._get_db()
        if not rag and not client and not db:
            return None
        
        try:
            # Build query from distill metadata
            query_parts = []
            if distill.metadata.get("company"):
                query_parts.append(distill.metadata["company"])
            if distill.metadata.get("industry"):
                query_parts.append(distill.metadata["industry"])
            if distill.metadata.get("summary"):
                query_parts.append(distill.metadata["summary"][:200])
            
            # Add key facts
            for fact in distill.facts[:5]:
                if isinstance(fact, dict):
                    query_parts.append(str(fact.get("concept", "")))
                else:
                    query_parts.append(str(fact)[:100])
            
            query = " ".join(query_parts)[:500]
            
            if not query.strip():
                query = "financial analysis market risk"

            context = rag.retrieve(query, k=5, threshold=0.6) if rag else None
            
            case_context = ""
            try:
                searcher = CaseEmbeddingSearch(self._get_supabase_client())
                case_results = searcher.search(query_text=query, limit=3)
                case_context = CaseEmbeddingSearch.format_context(case_results)
            except Exception:
                case_context = ""

            # Store in trace
            trace["rag_context"] = {
                "query": query,
                "results_count": (len(context.results) if context else 0),
                "total_tokens": (context.total_tokens if context else 0),
                "top_similarities": ([r.similarity for r in context.results[:3]] if context else []),
                "chunk_ids": ([r.chunk_id for r in context.results] if context else []),
            }
            evidence_ids = [r.chunk_id for r in (context.results if context else []) if r.chunk_id]
            for f in distill.facts:
                if not isinstance(f, dict):
                    continue
                doc_id = (f.get("evidence") or {}).get("document_id")
                if doc_id:
                    evidence_ids.append(str(doc_id))
            trace["evidence_ids"] = list(dict.fromkeys(evidence_ids))

            combined = ""
            if context and rag:
                combined = rag.format_context(context)

            # Keyword fallback on canonical Spoke C store (works on-prem too)
            if not combined.strip():
                from app.services.spoke_c_context_search import (
                    search_spoke_c_context,
                    search_spoke_c_context_supabase,
                    format_spoke_c_context,
                )
                rows = []
                if client:
                    rows = search_spoke_c_context_supabase(client=client, query=query, limit=5)
                if not rows:
                    rows = search_spoke_c_context(db=db, query=query, limit=5)
                if rows:
                    combined = format_spoke_c_context(rows)

            if case_context:
                combined = (combined + "\n\n" + case_context).strip() if combined else case_context

            return combined.strip() if combined else None
            
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            trace["rag_context"] = {"error": str(e)}
            return None
    
    async def _get_causal_context(
        self,
        distill: DistillResult,
        trace: Dict[str, Any],
    ) -> Optional[str]:
        """Get causal analysis context."""
        causal = self._get_causal_engine()
        if not causal:
            return None
        
        try:
            # Determine what to analyze based on distill
            scenarios = []
            
            # Check for macro indicators in facts
            macro_indicators = {
                "interest_rate": ("Fed_Funds_Rate", 0.25),
                "inflation": ("Inflation_CPI", 0.01),
                "gdp": ("GDP_Growth", -0.01),
                "unemployment": ("Unemployment_Rate", 0.005),
            }
            
            for fact in distill.facts[:10]:
                if isinstance(fact, dict):
                    concept = str(fact.get("concept", "")).lower()
                    for key, (node_name, change) in macro_indicators.items():
                        if key in concept:
                            scenarios.append((node_name, change))
                            break
            
            # Default: Fed rate scenario if nothing found
            if not scenarios:
                scenarios = [("Fed_Funds_Rate", 0.25)]
            
            # Run counterfactual for first scenario
            node_name, change = scenarios[0]
            result = causal.counterfactual(node_name, change)
            
            # Store in trace
            trace["causal_analysis"] = {
                "scenario": result.scenario,
                "impacts_count": len(result.impacts),
                "top_impacts": result.impacts[:5],
            }
            
            return causal.format_context(result)
            
        except Exception as e:
            logger.warning(f"Causal analysis failed: {e}")
            trace["causal_analysis"] = {"error": str(e)}
            return None

    async def _get_graph_context(
        self,
        distill: DistillResult,
        trace: Dict[str, Any],
    ) -> Optional[str]:
        """Get 3-hop graph reasoning context."""
        try:
            client = self._get_supabase_client()
            db = self._get_db()

            # Find entity by name
            company = distill.metadata.get("company") or distill.metadata.get("entity")
            if not company:
                return None
            if client:
                from app.services.graph_reasoning import GraphReasoningService
                entity_rows = (
                    client.table("ops_entities")
                    .select("id,name")
                    .ilike("name", f"%{company}%")
                    .limit(1)
                    .execute()
                ).data or []
                if not entity_rows:
                    return None
                entity_id = entity_rows[0].get("id")
                if not entity_id:
                    return None

                gr = GraphReasoningService(client)
                paths = gr.find_three_hop_paths(entity_id, max_hops=3, limit=10)
                trace["graph_paths"] = {"mode": "kg_relationships", "entity_id": entity_id, "paths_count": len(paths), "paths": paths}
                if not paths:
                    return None
                lines = ["[Graph 3-Hop Paths]"]
                for idx, p in enumerate(paths[:5], 1):
                    chain = " -> ".join([step["to"] for step in p["steps"]])
                    lines.append(f"{idx}. {p['start']} -> {chain} (hops={p['hops']})")
                return "\n".join(lines)

            # On-prem fallback: reason over Spoke D triples directly.
            if not db:
                return None
            from app.services.graph_reasoning_local import (
                find_three_hop_paths_from_triples,
                format_three_hop_paths,
            )
            triples = db.list_graph_triples(limit=500) or []
            paths = find_three_hop_paths_from_triples(start_node=str(company), triples=triples, max_hops=3, limit=10)
            trace["graph_paths"] = {"mode": "spoke_d_graph", "start": company, "paths_count": len(paths)}
            text = format_three_hop_paths(paths)
            return text or None
        except Exception as e:
            trace["graph_paths"] = {"error": str(e)}
            return None
    
    async def _get_oracle_context(
        self,
        distill: DistillResult,
        trace: Dict[str, Any],
    ) -> Optional[str]:
        """Get Oracle shock analysis (v17.5 integration)."""
        try:
            from app.services.oracle import fed_shock_analyzer
            from decimal import Decimal
            
            industry = distill.metadata.get("industry", "General Corporate")
            net_income = Decimal("0")
            
            for f in distill.facts:
                if isinstance(f, dict) and "netincome" in str(f.get("concept", "")).lower():
                    net_income = Decimal(str(f.get("value", "0")))
                    break
            
            if net_income > 0:
                impact = await fed_shock_analyzer.calculate_shock_impact(industry, net_income)
                oracle_text = fed_shock_analyzer.get_scenario_text(impact, "Net Income")
                
                trace["oracle_insight"] = {
                    "industry": industry,
                    "net_income": float(net_income),
                    "impact": impact,
                }
                
                return oracle_text
                
        except Exception as e:
            logger.warning(f"Oracle integration failed: {e}")
            trace["oracle_insight"] = {"error": str(e)}
        
        return None
    
    async def _enrich_with_ai_brain(
        self,
        distill: DistillResult,
        result: DecisionResult,
        trace: Dict[str, Any],
    ) -> DecisionResult:
        """Enrich a fallback result with AI Brain context."""
        # Get RAG context
        rag_context = await self._get_rag_context(distill, trace)
        
        # Get causal context
        causal_context = await self._get_causal_context(distill, trace)
        
        # Get oracle context
        oracle_context = await self._get_oracle_context(distill, trace)
        
        # Enhance rationale if we have context
        enhanced_rationale = result.rationale
        
        if rag_context or causal_context or oracle_context:
            enhanced_rationale += "\n\n[AI Brain Analysis]"
            
            if trace.get("rag_context") and not trace["rag_context"].get("error"):
                enhanced_rationale += f"\n• Retrieved {trace['rag_context'].get('results_count', 0)} relevant documents"
            
            if trace.get("causal_analysis") and not trace["causal_analysis"].get("error"):
                enhanced_rationale += f"\n• Causal scenario: {trace['causal_analysis'].get('scenario', 'N/A')}"
                impacts = trace["causal_analysis"].get("impacts_count", 0)
                if impacts:
                    enhanced_rationale += f" ({impacts} downstream effects identified)"
            
            if trace.get("oracle_insight") and not trace["oracle_insight"].get("error"):
                enhanced_rationale += f"\n• Oracle: Fed shock analysis for {trace['oracle_insight'].get('industry', 'N/A')}"
        
        decision_result = DecisionResult(
            decision=result.decision,
            rationale=enhanced_rationale,
            actions=result.actions,
            approvals=result.approvals,
            trace=trace,
            selfcheck=result.selfcheck,
        )
        self._log_rag_faithfulness(decision_result, trace)
        return decision_result

    def _log_rag_faithfulness(self, decision: DecisionResult, trace: Dict[str, Any]) -> None:
        try:
            rag_meta = trace.get("rag_context") or {}
            if rag_meta.get("error"):
                return
            rationale = (decision.rationale or "").lower()
            hits = 0
            for token in rationale.split()[:100]:
                if token in str(rag_meta).lower():
                    hits += 1
            faithfulness = hits / max(1, len(rationale.split()[:100]))
            from app.services.metrics_logger import MetricsLogger
            MetricsLogger().log("rag.faithfulness", faithfulness, {})
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)

    def _build_message(self, distill: DistillResult) -> str:
        """Legacy message builder (kept for compatibility)."""
        facts = distill.facts[:20]
        facts_lines = "\n".join([f"- {f}" for f in facts])
        cot = distill.cot_markdown[:2000]
        return (
            "You are FinRobot. Use the extracted facts and CoT to produce a decision summary.\n\n"
            "Facts (sample):\n"
            f"{facts_lines}\n\n"
            "CoT (excerpt):\n"
            f"{cot}\n\n"
            "Return a concise decision with risks and recommended actions."
        )

    def _fallback(self, distill: DistillResult) -> DecisionResult:
        rationale = "Auto-generated decision based on extracted facts."
        if distill.metadata.get("summary"):
            rationale = distill.metadata.get("summary")
        return DecisionResult(
            decision="Review",
            rationale=rationale,
            actions=[{"type": "request_more_info", "priority": "medium"}],
            approvals=[{"role": "analyst", "required": True}],
        )

    def _attach_selfcheck(
        self,
        distill: DistillResult,
        result: DecisionResult,
        trace: Dict[str, Any],
    ) -> None:
        try:
            from app.services.selfcheck import SelfCheckService
            service = SelfCheckService()
            check = service.evaluate(result, distill)
            result.selfcheck = check
            trace["selfcheck"] = check
            self._save_selfcheck(distill.metadata.get("case_id", ""), check, result.decision)
        except Exception as exc:
            logger.warning(f"SelfCheck failed: {exc}")

    def _save_selfcheck(self, case_id: str, check: Dict[str, Any], decision: str) -> None:
        try:
            client = self._get_supabase_client()
            if not client:
                return
            client.table("selfcheck_samples").insert({
                "case_id": case_id,
                "decision": decision,
                "consistency_score": check.get("consistency_score"),
                "confidence_level": check.get("confidence_level"),
                "field_checks": check.get("field_checks"),
            }).execute()
        except Exception as exc:
            logger.warning(f"Failed to save selfcheck sample: {exc}")
