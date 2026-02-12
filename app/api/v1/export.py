import csv
import io
import json
import zipfile
from hashlib import sha256
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.db.registry import get_db

router = APIRouter(prefix='/export', tags=['export'])


@router.get('')
async def export_case(case_id: str, format: str, include_cot: bool = False):
    db = get_db()
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail='case not found')
    distill = case.get('distill')
    if not distill:
        raise HTTPException(status_code=400, detail='distill required')

    facts = distill.facts if hasattr(distill, 'facts') else distill.get('facts', [])
    cot = distill.cot_markdown if hasattr(distill, 'cot_markdown') else distill.get('cot_markdown')

    if format.lower() == 'json':
        payload = {"case_id": case_id, "facts": facts}
        if include_cot:
            payload['cot_markdown'] = cot
        data = json.dumps(payload, ensure_ascii=False)
        return StreamingResponse(io.BytesIO(data.encode('utf-8')), media_type='application/json')

    if format.lower() != 'csv':
        raise HTTPException(status_code=400, detail='format must be csv or json')

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['fact_type', 'fact_key', 'fact_value', 'confidence_score'])
    for fact in facts:
        if isinstance(fact, dict):
            writer.writerow([
                fact.get('fact_type') or fact.get('type'),
                fact.get('fact_key') or fact.get('concept'),
                fact.get('fact_value') or fact.get('value'),
                fact.get('confidence_score') or fact.get('confidence'),
            ])
        else:
            writer.writerow(['text', None, str(fact), None])

    if include_cot and cot:
        writer.writerow([])
        writer.writerow(['cot_markdown'])
        writer.writerow([cot])

    output.seek(0)
    return StreamingResponse(io.BytesIO(output.getvalue().encode('utf-8')), media_type='text/csv')


@router.get("/bundle")
async def export_case_bundle(case_id: str):
    db = get_db()
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")

    bundle: Dict[str, Any] = {
        "case": case,
        "documents": db.list_documents(),
        "audit_logs": db.list_audit_logs(limit=500),
    }
    try:
        bundle["rag_context"] = db.list_rag_context(limit=200)
    except Exception:
        bundle["rag_context"] = []
    try:
        bundle["graph_triples"] = db.list_graph_triples(limit=200)
    except Exception:
        bundle["graph_triples"] = []

    manifest = {}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, data in bundle.items():
            payload = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            digest = sha256(payload).hexdigest()
            filename = f"{key}.json"
            zf.writestr(filename, payload)
            manifest[filename] = {"sha256": digest, "bytes": len(payload)}
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/zip")
