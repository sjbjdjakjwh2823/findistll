import json
import os
import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class RuntimeManager:
    """
    v17.0 Self-Healing Runtime: Handles checkpoints and confidence filtering.
    """
    
    CHECKPOINT_FILE = "checkpoints.json"
    CONFIDENCE_THRESHOLD = 0.5
    
    @classmethod
    def load_checkpoint(cls) -> Dict[str, Any]:
        if os.path.exists(cls.CHECKPOINT_FILE):
            try:
                with open(cls.CHECKPOINT_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")
        return {"processed_files": [], "last_run": None}

    @classmethod
    def save_checkpoint(cls, filename: str, status: str = "success"):
        data = cls.load_checkpoint()
        if filename not in data.get("processed_files", []):
            data.setdefault("processed_files", []).append(filename)
        data["last_run"] = datetime.now().isoformat()
        
        try:
            with open(cls.CHECKPOINT_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    @classmethod
    def filter_low_confidence(cls, facts: List[Any]) -> Tuple[List[Any], List[Any]]:
        """
        Filters facts based on v17.0 Confidence Score.
        Returns: (high_confidence_facts, low_confidence_facts)
        """
        high_conf = []
        low_conf = []
        
        for f in facts:
            # Check for confidence_score attribute (added in v16.0/v17.0)
            score = getattr(f, "confidence_score", 1.0)
            
            if score >= cls.CONFIDENCE_THRESHOLD:
                high_conf.append(f)
            else:
                low_conf.append(f)
                
        if low_conf:
            logger.warning(f"Filtered {len(low_conf)} low confidence facts (Score < {cls.CONFIDENCE_THRESHOLD})")
            
        return high_conf, low_conf
