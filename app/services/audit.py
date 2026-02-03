
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

class AuditVault:
    """
    Merkle-Chained Integrity System for Preciso.
    Ensures that every fact and decision is immutable and traceable.
    """
    
    @staticmethod
    def calculate_fact_hash(fact: Dict[str, Any]) -> str:
        """Calculates a deterministic SHA-256 hash for a fact."""
        # Focus on immutable semantic fields
        core_data = {
            "head": fact.get("head_node") or fact.get("entity"),
            "relation": fact.get("relation") or fact.get("metric"),
            "tail": fact.get("tail_node") or fact.get("value"),
            "period": fact.get("period") or fact.get("date"),
            "anchor": fact.get("source_anchor", {})
        }
        serialized = json.dumps(core_data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    @staticmethod
    def create_merkle_chain(events: List[Dict[str, Any]], prev_hash: str = "0"*64) -> List[Dict[str, Any]]:
        """
        Chains events together using hashes (Blockchain style).
        Each event's hash depends on the previous event's hash.
        """
        chained_events = []
        current_prev_hash = prev_hash
        
        for event in events:
            # Prepare data for hashing
            payload_str = json.dumps(event.get("payload", {}), sort_keys=True)
            timestamp = event.get("created_at") or datetime.now(timezone.utc).isoformat()
            
            # Chain: Hash(Payload + Timestamp + PrevHash)
            header = f"{payload_str}|{timestamp}|{current_prev_hash}"
            event_hash = hashlib.sha256(header.encode()).hexdigest()
            
            chained_event = dict(event)
            chained_event["event_hash"] = event_hash
            chained_event["prev_hash"] = current_prev_hash
            chained_event["integrity_version"] = "v1.0"
            
            chained_events.append(chained_event)
            current_prev_hash = event_hash
            
        return chained_events

    @staticmethod
    def verify_chain(chained_events: List[Dict[str, Any]], expected_prev_hash: str = "0"*64) -> bool:
        """Verifies the integrity of an entire chain of events."""
        current_prev_hash = expected_prev_hash
        
        for event in chained_events:
            if event.get("prev_hash") != current_prev_hash:
                return False
                
            payload_str = json.dumps(event.get("payload", {}), sort_keys=True)
            timestamp = event.get("created_at")
            header = f"{payload_str}|{timestamp}|{current_prev_hash}"
            calculated_hash = hashlib.sha256(header.encode()).hexdigest()
            
            if event.get("event_hash") != calculated_hash:
                return False
                
            current_prev_hash = calculated_hash
            
        return True
