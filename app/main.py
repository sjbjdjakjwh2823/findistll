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
    OracleSimulateRequest,
    GraphDataResponse,
)
from app.services.distill_engine import FinDistillAdapter
from app.services.oracle import OracleEngine
from app.services.robot_engine import FinRobotAdapter
from app.services.orchestrator import Orchestrator
from app.services.spokes import SpokesEngine
from app.services.toolkit import PrecisoToolkit

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
_toolkit = PrecisoToolkit()

app.mount("/ui", StaticFiles(directory="app/ui"), name="ui")
app.mount("/_next", StaticFiles(directory="app/ui/_next"), name="next")


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


@app.get("/evidence", response_class=HTMLResponse)
@app.get("/evidence.html", response_class=HTMLResponse)
def ui_evidence():
    return _html_response("evidence.html")


@app.get("/analytics", response_class=HTMLResponse)
@app.get("/analytics.html", response_class=HTMLResponse)
def ui_analytics():
    return _html_response("analytics.html")


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


@app.post("/oracle/simulate")
async def oracle_simulate(payload: OracleSimulateRequest):
    edges = []
    if payload.case_id:
        edges = _db.list_graph_edges(payload.case_id)
        if not edges:
            case = _db.get_case(payload.case_id)
            if case and case.get("distill"):
                # Handle both dict and object if distill is saved differently
                distill = case["distill"]
                if hasattr(distill, "facts"):
                    edges = distill.facts
                elif isinstance(distill, dict):
                    edges = distill.get("facts", [])
    else:
        all_cases = _db.list_cases()
        for case in all_cases:
            cid = case.get("case_id")
            if cid:
                case_edges = _db.list_graph_edges(cid)
                if case_edges:
                    edges.extend(case_edges)
                elif case.get("distill"):
                    distill = case["distill"]
                    if hasattr(distill, "facts"):
                        edges.extend(distill.facts)
                    elif isinstance(distill, dict):
                        edges.extend(distill.get("facts", []))

    causal_graph = _oracle.build_causal_skeleton(edges)
    result = _oracle.simulate_what_if(
        node_id=payload.node_id,
        value_delta=payload.value_delta,
        causal_graph=causal_graph,
        horizon_steps=payload.horizon_steps
    )
    return result


@app.get("/graph/data", response_model=GraphDataResponse)
async def get_graph_data(case_id: str = None):
    edges = []
    if case_id:
        edges = _db.list_graph_edges(case_id)
        if not edges:
            case = _db.get_case(case_id)
            if case and case.get("distill"):
                distill = case["distill"]
                if hasattr(distill, "facts"):
                    edges = distill.facts
                elif isinstance(distill, dict):
                    edges = distill.get("facts", [])
    else:
        all_cases = _db.list_cases()
        for case in all_cases:
            cid = case.get("case_id")
            if cid:
                case_edges = _db.list_graph_edges(cid)
                if case_edges:
                    edges.extend(case_edges)
                elif case.get("distill"):
                    distill = case["distill"]
                    if hasattr(distill, "facts"):
                        edges.extend(distill.facts)
                    elif isinstance(distill, dict):
                        edges.extend(distill.get("facts", []))

    causal_graph = _oracle.build_causal_skeleton(edges)
    
    nodes_map = {}
    links = []
    
    for link in causal_graph:
        source = link.get("head_node")
        target = link.get("tail_node")
        if not source or not target:
            continue
            
        if source not in nodes_map:
            nodes_map[source] = {
                "id": source, 
                "label": source, 
                "group": (link.get("head_object") or {}).get("object_type", "entity"),
                "attributes": (link.get("head_object") or {}).get("attributes", {})
            }
        if target not in nodes_map:
            nodes_map[target] = {
                "id": target, 
                "label": target, 
                "group": (link.get("tail_object") or {}).get("object_type", "metric"),
                "attributes": (link.get("tail_object") or {}).get("attributes", {})
            }
            
        links.append({
            "source": source,
            "target": target,
            "value": float(link.get("strength", 0.5)),
            "polarity": float(link.get("polarity", 1.0)),
            "relation": link.get("relation")
        })
        
    return {
        "nodes": list(nodes_map.values()),
        "links": links
    }


@app.get("/cases/{case_id}")
def get_case(case_id: str):
    case = _db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    return case


# --- B2B TOOLKIT API ENDPOINTS ---

@app.post("/api/v1/toolkit/distill")
async def toolkit_distill(payload: Dict[str, Any]):
    """B2B Endpoint for high-precision data extraction."""
    # Logic to handle raw data or base64
    content_b64 = payload.get("content_base64")
    if not content_b64:
        raise HTTPException(status_code=400, detail="content_base64 required")
    
    file_bytes = base64.b64decode(content_b64)
    filename = payload.get("filename", "api_upload.pdf")
    mime_type = payload.get("mime_type", "application/pdf")
    
    result = await _toolkit.distill_document(file_bytes, filename, mime_type)
    return result

@app.post("/api/v1/toolkit/predict")
async def toolkit_predict(payload: Dict[str, Any]):
    """B2B Endpoint for causal impact simulation."""
    node_id = payload.get("node_id")
    delta = payload.get("delta", 1.0)
    causal_graph = payload.get("causal_graph", [])
    
    if not node_id:
        raise HTTPException(status_code=400, detail="node_id required")
        
    return _toolkit.predict_impact(node_id, delta, causal_graph)

@app.post("/api/v1/toolkit/verify")
async def toolkit_verify(payload: Dict[str, Any]):
    """B2B Endpoint for cryptographic integrity check."""
    chain = payload.get("event_chain", [])
    if not chain:
        raise HTTPException(status_code=400, detail="event_chain required")
        
    is_valid = _toolkit.verify_integrity(chain)
    return {"integrity_valid": is_valid}
