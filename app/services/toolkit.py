from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.services.distill_engine import FinDistillAdapter
from app.services.oracle import OracleEngine
from app.services.agentic_brain import AgenticBrain
from app.services.audit import AuditVault
from app.services.zkp_validator import ZKPValidator

class PrecisoToolkit:
    """
    B2B-ready Toolkit Interface.
    Exposes Preciso's core engines as modular APIs for enterprise integration.
    """
    
    def __init__(self):
        self.distill = FinDistillAdapter()
        self.oracle = OracleEngine()
        self.brain = AgenticBrain()
        self.vault = AuditVault()
        self.zkp = ZKPValidator()
        self._current_chain_hash = "0" * 64
        self._audit_events: List[Dict[str, Any]] = []

    def log_sovereign_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        stage: Optional[str] = None,
        status: str = "recorded",
        case_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an immutable, Merkle-chained audit event."""
        event = {
            "case_id": case_id or "toolkit",
            "event_type": event_type,
            "stage": stage,
            "status": status,
            "payload": payload or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        chained = self.vault.create_merkle_chain([event], prev_hash=self._current_chain_hash)[0]
        self._current_chain_hash = chained["event_hash"]
        self._audit_events.append(chained)
        return chained

    async def distill_document(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        zkp_proof: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Preciso Distill: High-precision data extraction with pixel lineage."""
        self.log_sovereign_event(
            event_type="inference_request",
            stage="distill",
            payload={
                "filename": filename,
                "mime_type": mime_type,
                "source": "api_toolkit",
                "bytes_len": len(file_bytes),
                "zkp_proof_present": zkp_proof is not None,
            },
        )
        document = {
            "file_bytes": file_bytes,
            "filename": filename,
            "mime_type": mime_type,
            "source": "api_toolkit",
            "metadata": {"zkp_proof": zkp_proof} if zkp_proof is not None else {},
        }
        result = await self.distill.extract(document)
        return {
            "facts": result.facts,
            "summary": result.metadata.get("summary"),
            "reflection_log": result.metadata.get("self_reflection"),
            "status": "success"
        }

    def predict_impact(self, node_id: str, delta: float, causal_graph: List[Dict]) -> Dict[str, Any]:
        """Preciso Oracle: Causal impact simulation (What-if)."""
        self.log_sovereign_event(
            event_type="inference_request",
            stage="oracle",
            payload={
                "node_id": node_id,
                "delta": delta,
                "causal_graph_links": len(causal_graph),
            },
        )
        return self.oracle.simulate_what_if(node_id, delta, causal_graph)

    async def generate_strategy(self, distill_result: Any) -> Dict[str, Any]:
        """Preciso Agentic Brain: Tri-agent collaborative reasoning."""
        decision = await self.brain.process_collaboration(distill_result)
        self.log_sovereign_event(
            event_type="action_proposal",
            stage="decision",
            payload={
                "recommendation": decision.decision,
                "actions_count": len(decision.actions or []),
            },
        )
        return {
            "recommendation": decision.decision,
            "rationale": decision.rationale,
            "suggested_actions": decision.actions
        }

    def verify_integrity(self, event_chain: List[Dict]) -> bool:
        """Preciso Sovereign Vault: Cryptographic integrity verification."""
        return self.vault.verify_chain(event_chain)

    def verify_external_data(
        self,
        provider_id: str,
        proof: Dict[str, Any],
        public_signals: List[Any],
        verification_key: Dict[str, Any],
        scheme: str = "groth16",
        circuit_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validate external data integrity using a mock ZKP verifier."""
        verification = self.zkp.verify_proof(
            proof=proof,
            public_signals=public_signals,
            verification_key=verification_key,
            scheme=scheme,
            circuit_id=circuit_id,
        )
        self.log_sovereign_event(
            event_type="zkp_verification",
            stage="zkp",
            status="verified" if verification["valid"] else "rejected",
            payload={
                "provider_id": provider_id,
                "scheme": verification["scheme"],
                "circuit_id": verification["circuit_id"],
                "proof_hash": verification["proof_hash"],
                "signals_hash": verification["signals_hash"],
                "vk_hash": verification["vk_hash"],
                "checks": verification["checks"],
                "errors": verification["errors"],
                "metadata": metadata or {},
            },
        )
        return {
            "status": verification["status"],
            "verified": verification["valid"],
            "verification": verification,
        }

    def generate_compliance_report(self, limit: int = 50) -> Dict[str, Any]:
        """Aggregate recent audit logs into a compliance-focused summary."""
        recent_events = self._audit_events[-limit:] if limit and limit > 0 else []
        if recent_events:
            expected_prev_hash = recent_events[0].get("prev_hash", "0" * 64)
            merkle_root = recent_events[-1].get("event_hash")
            last_event_at = recent_events[-1].get("created_at")
            integrity_version = recent_events[-1].get("integrity_version", "v1.0")
            chain_verified = self.vault.verify_chain(recent_events, expected_prev_hash=expected_prev_hash)
        else:
            expected_prev_hash = "0" * 64
            merkle_root = self._current_chain_hash
            last_event_at = None
            integrity_version = "v1.0"
            chain_verified = True

        event_type_counts: Dict[str, int] = {}
        stage_counts: Dict[str, int] = {}
        for event in recent_events:
            event_type = event.get("event_type") or "unknown"
            stage = event.get("stage") or "unknown"
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        return {
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
            "events_reviewed": len(recent_events),
            "event_type_counts": event_type_counts,
            "stage_counts": stage_counts,
            "sovereign_proofs": {
                "merkle_root": merkle_root,
                "expected_prev_hash": expected_prev_hash,
                "chain_verified": chain_verified,
                "integrity_version": integrity_version,
                "last_event_at": last_event_at,
            },
            "recent_events": list(recent_events),
        }
