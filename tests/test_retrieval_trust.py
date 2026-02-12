from app.services.retrieval_trust import StructuredChunker
from app.services.multi_agent_framework import MultiAgentOrchestrator
from app.db.client import InMemoryDB
from app.services.types import DistillResult


def test_structured_chunker_splits_facts_and_cot():
    distill = DistillResult(
        facts=[{"concept": "DebtRatio", "value": "0.7"}],
        cot_markdown="## Risk Analysis\nHigh leverage.\n## Conclusion\nProceed with caution.",
        metadata={},
    )
    chunker = StructuredChunker()
    sections = chunker.chunk_distill(distill)
    assert any(section["chunk_type"] == "fact" for section in sections)
    cot_sections = [s for s in sections if s["chunk_type"] == "cot_section"]
    assert len(cot_sections) == 2


def test_multi_agent_manager_gating():
    db = InMemoryDB()
    orchestrator = MultiAgentOrchestrator(db=db, distill=None, robot=None)  # type: ignore[arg-type]
    decision = type(
        "Decision",
        (),
        {"decision": "Review", "rationale": "low confidence", "actions": [], "approvals": []},
    )
    report = {"confidence_score": 0.65}
    manager = orchestrator._compose_manager_decision(decision, report)
    assert manager["needs_review"] is True
