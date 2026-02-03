from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DistillResult:
    facts: List[Dict[str, Any]] = field(default_factory=list)
    cot_markdown: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_anchors: Dict[str, Any] = field(default_factory=dict) # Added for pixel lineage


@dataclass
class DecisionResult:
    decision: str
    rationale: str
    actions: List[Dict[str, Any]] = field(default_factory=list)
    approvals: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PipelineResult:
    case_id: str
    distill: DistillResult
    decision: DecisionResult
