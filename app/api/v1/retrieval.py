from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.retrieval_trust import HybridRetriever
from app.services.metrics_logger import MetricsLogger

router = APIRouter(prefix="/retrieval", tags=["Retrieval"])


class RetrievalSearchRequest(BaseModel):
    query: str = Field(..., description="Query text for retrieval")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    top_k: int = Field(10, ge=1, le=50)
    use_graph_expansion: bool = True


@router.post("/search")
def hybrid_search(payload: RetrievalSearchRequest):
    try:
        retriever = HybridRetriever()
        result = retriever.search(
            query_text=payload.query,
            filters=payload.filters or {},
            top_k=payload.top_k,
            use_graph_expansion=payload.use_graph_expansion,
        )
        MetricsLogger().log(
            "retrieval_hybrid_latency_ms",
            float(result.get("latency_ms", 0)),
            tags={"filter_keys": ",".join(sorted((payload.filters or {}).keys()))},
        )
        return result
    except RuntimeError as exc:
        # Graceful fallback when Supabase is not configured.
        return {
            "results": [],
            "latency_ms": 0,
            "filters": payload.filters or {},
            "warning": str(exc),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
