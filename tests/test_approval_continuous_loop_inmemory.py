from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_approval_triggers_spoke_cd_without_supabase_client(monkeypatch) -> None:
    """
    Regression guard:
    - InMemoryDB does not expose a Supabase `.client`.
    - Approval endpoint must still succeed and store RAG context + graph triples without crashing.
    """
    # Ensure we use InMemoryDB (no Supabase env)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    # Build a minimal FastAPI app that avoids optional multipart deps.
    from app.api.v1 import approval  # noqa: WPS433
    from app.db.client import InMemoryDB  # noqa: WPS433
    from app.db.registry import set_db, get_db  # noqa: WPS433
    from app.core import auth  # noqa: WPS433
    from app.core import rbac  # noqa: WPS433

    app = FastAPI()
    set_db(InMemoryDB())
    app.include_router(approval.router, prefix="/api/v1")

    client = TestClient(app)
    db = get_db()

    case_id = db.create_case({"title": "Test Case"})
    # Minimal distill payload that triggers spoke context/triples generation.
    distill = {
        "facts": [
            {
                "entity": "ACME",
                "metric": "revenue",
                "period": "2024",
                "value": "1.0",
                "source": "test",
                "evidence": {"document_id": "doc1", "method": "unit"},
            }
        ],
        "cot_markdown": "Revenue increased due to stronger demand.",
        "metadata": {"doc_id": "doc1", "source": "unit"},
    }
    db.cases[case_id]["distill"] = distill  # type: ignore[index]
    db.cases[case_id]["decision"] = {"decision": "approve"}  # type: ignore[index]

    class _User:
        user_id = "u1"
        role = "admin"

    app.dependency_overrides[auth.get_current_user] = lambda: _User()
    app.dependency_overrides[rbac.has_permission] = lambda *_args, **_kwargs: True

    resp = client.post(
        f"/api/v1/approvals/cases/{case_id}/approve",
        json={"decision": {"decision": "approved"}, "reasoning": "ok", "confidence_score": 0.99},
    )
    assert resp.status_code == 200, resp.text

    # verify contexts persisted to InMemoryDB
    rag = db.list_rag_context(limit=50)
    assert rag, "expected spoke_c_rag_context records saved"

    triples = db.list_graph_triples(limit=50)
    assert triples, "expected spoke_d_graph triples saved"
