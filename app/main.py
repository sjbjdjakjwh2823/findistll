from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import load_settings
from app.db.client import InMemoryDB
from app.db.supabase_db import SupabaseDB
from app.models.schemas import (
    CaseCreate,
    DocumentCreate,
    DistillResponse,
    DecisionResponse,
    PipelineResponse,
)
from app.services.distill_engine import FinDistillAdapter
from app.services.oracle import OracleEngine
from app.services.robot_engine import FinRobotAdapter
from app.services.orchestrator import Orchestrator
from app.services.spokes import SpokesEngine

settings = load_settings()


def init_db():
    if settings.supabase_url and settings.supabase_service_role_key:
        return SupabaseDB(settings.supabase_url, settings.supabase_service_role_key)
    return InMemoryDB()


app = FastAPI(title="Preciso Core", version="0.1.0")

_db = init_db()
_distill = FinDistillAdapter()
_robot = FinRobotAdapter()
_spokes = SpokesEngine()
_oracle = OracleEngine()
_orchestrator = Orchestrator(_db, _distill, _robot, _spokes, _oracle)

app.mount("/ui", StaticFiles(directory="app/ui"), name="ui")


def _load_ui(page: str) -> str:
    with open(f"app/ui/{page}", "r", encoding="utf-8") as f:
        return f.read()

def _html_response(page: str) -> HTMLResponse:
    content = _load_ui(page)
    return HTMLResponse(
        content=content,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )

@app.get("/", response_class=HTMLResponse)
def ui_root():
    return _html_response("index.html")


@app.get("/decisions", response_class=HTMLResponse)
@app.get("/decisions.html", response_class=HTMLResponse)
def ui_decisions():
    return _html_response("decisions.html")


@app.get("/cases", response_class=HTMLResponse)
@app.get("/cases.html", response_class=HTMLResponse)
def ui_cases():
    return _html_response("cases.html")


@app.get("/graph", response_class=HTMLResponse)
@app.get("/graph.html", response_class=HTMLResponse)
def ui_graph():
    return _html_response("graph.html")


@app.get("/cases/sample-case", response_class=HTMLResponse)
def ui_case_detail():
    return _html_response("cases/sample-case.html")


@app.get("/audit", response_class=HTMLResponse)
@app.get("/audit.html", response_class=HTMLResponse)
def ui_audit():
    return _html_response("audit.html")


@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin.html", response_class=HTMLResponse)
def ui_admin():
    return _html_response("admin.html")


@app.get("/debug.html", response_class=HTMLResponse)
def ui_debug():
    return _html_response("debug.html")


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.app_env, "domain": settings.public_domain}

@app.get("/plain", response_class=PlainTextResponse)
def plain():
    return PlainTextResponse("PRECISO OK", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    })

@app.get("/simple", response_class=HTMLResponse)
def simple():
    html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Preciso Simple</title>
    <style>
      html, body { margin: 0; padding: 0; background: #ffffff; color: #111111; font-family: Arial, sans-serif; }
      .wrap { padding: 32px; }
      h1 { font-size: 28px; margin: 0 0 12px; }
      p { font-size: 16px; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>PRECISO SIMPLE OK</h1>
      <p>If you see this, rendering works.</p>
    </div>
  </body>
</html>"""
    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.post("/cases")
def create_case(payload: CaseCreate):
    case_id = _db.create_case({"title": payload.title})
    return {"case_id": case_id}


@app.get("/cases")
def list_cases():
    return _db.list_cases()


@app.get("/documents")
def list_documents():
    return _db.list_documents()


@app.post("/cases/{case_id}/documents")
def add_document(case_id: str, payload: DocumentCreate):
    if not _db.get_case(case_id):
        raise HTTPException(status_code=404, detail="case not found")
    doc_id = _db.add_document(case_id, payload.dict())
    return {"doc_id": doc_id}


@app.post("/cases/{case_id}/distill", response_model=DistillResponse)
async def distill(case_id: str):
    case = _db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    if not case.get("documents"):
        raise HTTPException(status_code=400, detail="no documents")
    doc_id = case["documents"][0]
    document = _db.docs.get(doc_id, {}) if hasattr(_db, "docs") else {}
    if not document:
        documents = _db.list_documents()
        document = next((d.get("payload", {}) for d in documents if d.get("doc_id") == doc_id), {})
    distill_result = await _distill.extract(document)
    _db.save_distill(case_id, distill_result)
    return DistillResponse(
        facts=distill_result.facts,
        cot_markdown=distill_result.cot_markdown,
        metadata=distill_result.metadata,
    )


@app.post("/cases/{case_id}/decide", response_model=DecisionResponse)
def decide(case_id: str):
    case = _db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    distill_result = case.get("distill")
    if not distill_result:
        raise HTTPException(status_code=400, detail="distill required")
    decision_result = _robot.decide(distill_result)
    _db.save_decision(case_id, decision_result)
    return DecisionResponse(
        decision=decision_result.decision,
        rationale=decision_result.rationale,
        actions=decision_result.actions,
        approvals=decision_result.approvals,
    )


@app.post("/cases/{case_id}/run", response_model=PipelineResponse)
async def run_pipeline(case_id: str):
    case = _db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    if not case.get("documents"):
        raise HTTPException(status_code=400, detail="no documents")
    doc_id = case["documents"][0]
    document = _db.docs.get(doc_id, {}) if hasattr(_db, "docs") else {}
    if not document:
        documents = _db.list_documents()
        document = next((d.get("payload", {}) for d in documents if d.get("doc_id") == doc_id), {})

    result = await _orchestrator.run(case_id, document)
    return PipelineResponse(
        case_id=result.case_id,
        distill=DistillResponse(
            facts=result.distill.facts,
            cot_markdown=result.distill.cot_markdown,
            metadata=result.distill.metadata,
        ),
        decision=DecisionResponse(
            decision=result.decision.decision,
            rationale=result.decision.rationale,
            actions=result.decision.actions,
            approvals=result.decision.approvals,
        ),
    )


@app.get("/cases/{case_id}")
def get_case(case_id: str):
    case = _db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    return case
