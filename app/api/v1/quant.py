from __future__ import annotations

import base64
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.db.registry import get_db

router = APIRouter(prefix="/quant", tags=["WS8 - Quant"])


@router.get("/artifact")
def download_spoke_b_artifact(
    doc_id: str = Query(...),
    kind: str = Query(..., description="facts|tables|features"),
):
    db = get_db()
    artifact = db.get_spoke_b_artifact(doc_id, kind)
    if not artifact:
        raise HTTPException(status_code=404, detail="artifact not found")
    b64 = artifact.get("content_base64") or ""
    try:
        raw = base64.b64decode(b64)
    except Exception:
        raise HTTPException(status_code=500, detail="invalid artifact encoding")
    filename = f"spoke_b_{kind}_{doc_id}.parquet"
    return StreamingResponse(
        io.BytesIO(raw),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename=\"{filename}\"'},
    )

