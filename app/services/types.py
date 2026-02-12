from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DistillResult:
    facts: List[Dict[str, Any]] = field(default_factory=list)
    cot_markdown: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionResult:
    decision: str
    rationale: str
    actions: List[Dict[str, Any]] = field(default_factory=list)
    approvals: List[Dict[str, Any]] = field(default_factory=list)
    trace: Optional[Dict[str, Any]] = None  # Phase 2: AI Brain traceability
    selfcheck: Optional[Dict[str, Any]] = None  # Phase 7.5: SelfCheck consistency


@dataclass
class PipelineResult:
    case_id: str
    distill: DistillResult
    decision: DecisionResult
