from typing import Optional

from fastapi import APIRouter

from app.services.orchestrator import Orchestrator
from app.services.metrics_logger import MetricsLogger

router = APIRouter(prefix="/metrics", tags=["Metrics"])

def _get_client():
    """
    Metrics are best-effort. If Supabase is not configured, return empty metrics
    rather than failing the API/UI.
    """
    return MetricsLogger()._get_client()  # noqa: SLF001 - internal reuse is intentional here.


@router.get("/recent")
def recent_metrics(limit: int = 50, name: Optional[str] = None, name_prefix: Optional[str] = None, tenant_id: Optional[str] = None):
    client = _get_client()
    if not client:
        return {"metrics": [], "note": "supabase_not_configured"}

    query = client.table("perf_metrics").select("*").order("created_at", desc=True).limit(limit)
    if name:
        query = query.eq("name", name)
    if name_prefix:
        query = query.ilike("name", f"{name_prefix}%")
    if tenant_id:
        query = query.contains("tags", {"tenant_id": tenant_id})
    res = query.execute()
    return {"metrics": res.data or []}


@router.get("")
@router.get("/")
def recent_metrics_alias(limit: int = 50, name: Optional[str] = None, name_prefix: Optional[str] = None, tenant_id: Optional[str] = None):
    # Backwards compatible route used by older UI code.
    return recent_metrics(limit=limit, name=name, name_prefix=name_prefix, tenant_id=tenant_id)


@router.get("/orchestration")
def orchestration_map():
    return {"tasks": Orchestrator.task_map()}


@router.get("/quality_gate")
def quality_gate_metrics(limit: int = 2000, tenant_id: Optional[str] = None):
    """
    Aggregate recent quality gate metrics stored in perf_metrics.
    """
    client = _get_client()
    if not client:
        return {"metrics": [], "note": "supabase_not_configured"}

    query = client.table("perf_metrics").select("*").order("created_at", desc=True).limit(limit)
    query = query.ilike("name", "quality_gate.%")
    if tenant_id:
        query = query.contains("tags", {"tenant_id": tenant_id})
    res = query.execute()
    rows = res.data or []

    summary: Dict[str, float] = {}
    for r in rows:
        name = r.get("name")
        value = r.get("value")
        if not name:
            continue
        try:
            summary[name] = summary.get(name, 0.0) + float(value or 0)
        except Exception:
            continue
    return {"summary": summary, "count": len(rows)}
