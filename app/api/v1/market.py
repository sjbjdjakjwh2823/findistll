"""
Market Data API - WS1 External Data Integration
Fetch + normalize market/FX/crypto/news data and optionally ingest to raw_documents.
"""

from typing import Optional
import json
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from app.services.market_data import market_data_service
from app.services.types import DistillResult
from app.services.spokes import build_rag_context, extract_graph_triples
from app.services.spoke_ab_service import SpokeABService
from app.core.tenant_context import get_effective_tenant_id
from app.services.spoke_c_rag import RAGEngine
from app.services.metrics_logger import MetricsLogger
from app.api.v1.ingest import get_db
from app.services.market_ingest import ingest_snapshot

router = APIRouter(prefix="/market", tags=["Market Data"])


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fallback_ingest(source: str, symbol: Optional[str], content: dict) -> str:
    """
    Fallback when Supabase tables are not bootstrapped/reachable.
    Stores the normalized snapshot locally so operators can recover it later.
    """
    out = {
        "id": f"local_{source}_{symbol or 'na'}_{int(datetime.now(timezone.utc).timestamp())}",
        "source": source,
        "symbol": symbol,
        "captured_at": _utc_now_iso(),
        "content": content,
    }
    p = Path(__file__).resolve().parents[3] / "artifacts" / "market_ingest_fallback.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=True) + "\n")
    return out["id"]


def _ingest_snapshot(source: str, symbol: Optional[str], content: dict) -> str:
    try:
        return ingest_snapshot(source, symbol, content)
    except Exception:
        return _fallback_ingest(source, symbol, content)


class EventIngestRequest(BaseModel):
    events: List[Dict[str, Any]] = Field(..., description="List of event objects")
    symbol: Optional[str] = Field(None, description="Optional entity symbol or region")


@router.get("/quote")
async def get_quote(symbol: str = Query(...), ingest: bool = Query(False)):
    db = get_db()
    payload = await market_data_service.fetch_finnhub_quote(symbol, db=db)
    if payload.get("error"):
        raise HTTPException(status_code=502, detail=payload.get("error"))
    normalized = market_data_service.normalize_market_snapshot(payload, "finnhub_quote", symbol=symbol)
    if ingest:
        doc_id = _ingest_snapshot("finnhub_quote", symbol, normalized)
        return {"doc_id": doc_id, "data": normalized}
    return {"data": normalized}


@router.get("/forex")
async def get_forex(base: str = Query("USD"), quote: str = Query("KRW"), ingest: bool = Query(False)):
    db = get_db()
    payload = await market_data_service.fetch_finnhub_forex(base, quote, db=db)
    if payload.get("error"):
        raise HTTPException(status_code=502, detail=payload.get("error"))
    symbol = f"{base}/{quote}"
    normalized = market_data_service.normalize_market_snapshot(payload, "finnhub_forex", symbol=symbol)
    if ingest:
        doc_id = _ingest_snapshot("finnhub_forex", symbol, normalized)
        return {"doc_id": doc_id, "data": normalized}
    return {"data": normalized}


@router.get("/crypto")
async def get_crypto(symbol: str = Query(...), ingest: bool = Query(False)):
    db = get_db()
    payload = await market_data_service.fetch_finnhub_crypto(symbol, db=db)
    if payload.get("error"):
        raise HTTPException(status_code=502, detail=payload.get("error"))
    normalized = market_data_service.normalize_market_snapshot(payload, "finnhub_crypto", symbol=symbol)
    if ingest:
        doc_id = _ingest_snapshot("finnhub_crypto", symbol, normalized)
        return {"doc_id": doc_id, "data": normalized}
    return {"data": normalized}


@router.get("/news")
async def get_news(category: str = Query("general"), symbol: Optional[str] = Query(None), ingest: bool = Query(False)):
    db = get_db()
    payload = await market_data_service.fetch_finnhub_news(category=category, symbol=symbol, db=db)
    normalized = {
        "facts": [],
        "metadata": {"source": "finnhub_news", "category": category, "symbol": symbol},
        "raw_payload": payload,
    }
    if ingest:
        doc_id = _ingest_snapshot("finnhub_news", symbol, normalized)
        return {"doc_id": doc_id, "data": normalized}
    return {"data": normalized}


@router.get("/fred/series")
async def get_fred_series(series_id: str = Query(...), limit: int = Query(5), ingest: bool = Query(False)):
    """
    Fetch + normalize FRED series observations.
    If ingest=true, stores normalized snapshot into raw_documents.
    """
    db = get_db()
    observations = await market_data_service.fetch_fred_series(series_id, limit=limit, db=db)
    if not observations:
        raise HTTPException(status_code=502, detail="fred_series_fetch_failed_or_empty")

    # Normalize expects series_id included per observation
    payload = [{**obs, "series_id": series_id} for obs in observations]
    normalized = market_data_service.normalize_market_snapshot(payload, "fred_series", symbol=series_id)

    if ingest:
        doc_id = _ingest_snapshot("fred_series", series_id, normalized)
        return {"doc_id": doc_id, "data": normalized}
    return {"data": normalized}


@router.get("/fred/key-rates")
async def get_fred_key_rates(ingest: bool = Query(False)):
    """
    Fetch a small bundle of key policy/rates series from FRED and normalize them.
    """
    db = get_db()
    rates = await market_data_service.get_key_rates(db=db)
    if not rates:
        raise HTTPException(status_code=502, detail="fred_key_rates_fetch_failed_or_empty")
    payload = []
    for _, item in rates.items():
        payload.append(
            {
                "series_id": item.get("series_id"),
                "date": item.get("date"),
                "value": item.get("value"),
            }
        )
    normalized = market_data_service.normalize_market_snapshot(payload, "fred_series", symbol="FRED_KEY_RATES")
    if ingest:
        doc_id = _ingest_snapshot("fred_series", "FRED_KEY_RATES", normalized)
        return {"doc_id": doc_id, "data": normalized}
    return {"data": normalized}


@router.get("/treasury")
async def get_treasury_yield(
    maturity: str = Query("10Y", description="Treasury maturity: 2Y, 5Y, 10Y, 30Y"),
    ingest: bool = Query(False),
):
    """
    Convenience endpoint for Treasury yields using FRED series.
    """
    series_map = {
        "2Y": "GS2",
        "5Y": "GS5",
        "10Y": "GS10",
        "30Y": "GS30",
    }
    series_id = series_map.get(maturity.upper())
    if not series_id:
        raise HTTPException(status_code=400, detail="unsupported_maturity")
    db = get_db()
    observations = await market_data_service.fetch_fred_series(series_id, limit=5, db=db)
    if not observations:
        raise HTTPException(status_code=502, detail="treasury_fetch_failed_or_empty")
    payload = [{**obs, "series_id": series_id} for obs in observations]
    normalized = market_data_service.normalize_market_snapshot(payload, "fred_series", symbol=series_id)
    if ingest:
        doc_id = _ingest_snapshot("fred_series", series_id, normalized)
        return {"doc_id": doc_id, "data": normalized}
    return {"data": normalized}


@router.get("/fmp/growth")
async def get_fmp_financial_growth(
    symbol: str = Query(..., description="Ticker symbol"),
    ingest: bool = Query(False),
):
    """
    Fetch Financial Modeling Prep financial statement growth and normalize.
    """
    db = get_db()
    payload = await market_data_service.fetch_fmp_financial_statement_growth(symbol, db=db)
    if not payload:
        raise HTTPException(status_code=502, detail="fmp_fetch_failed_or_empty")
    normalized = market_data_service.normalize_market_snapshot(payload, "fmp_financial_statement_growth", symbol=symbol)
    if ingest:
        doc_id = _ingest_snapshot("fmp_financial_statement_growth", symbol, normalized)
        return {"doc_id": doc_id, "data": normalized}
    return {"data": normalized}


@router.get("/sec/filings")
async def get_sec_filings(
    symbol: str = Query(..., description="Ticker symbol"),
    form_type: str = Query("10-Q", description="SEC form type"),
    limit: int = Query(5, ge=1, le=50),
    ingest: bool = Query(False),
):
    """
    Fetch SEC filings and normalize.
    """
    db = get_db()
    payload = await market_data_service.fetch_sec_filings(symbol, form_type=form_type, limit=limit, db=db)
    if not payload:
        raise HTTPException(status_code=502, detail="sec_fetch_failed_or_empty")
    normalized = market_data_service.normalize_market_snapshot(payload, "sec_filings", symbol=symbol)
    if ingest:
        doc_id = _ingest_snapshot("sec_filings", symbol, normalized)
        return {"doc_id": doc_id, "data": normalized}
    return {"data": normalized}


@router.get("/commodity")
async def get_commodity_series(
    series_id: str = Query(..., description="FRED commodity series id (e.g., DCOILWTICO, DHHNGSP)"),
    ingest: bool = Query(False),
):
    """
    Convenience endpoint for commodity series using FRED.
    """
    db = get_db()
    observations = await market_data_service.fetch_fred_series(series_id, limit=5, db=db)
    if not observations:
        raise HTTPException(status_code=502, detail="commodity_fetch_failed_or_empty")
    payload = [{**obs, "series_id": series_id} for obs in observations]
    normalized = market_data_service.normalize_market_snapshot(payload, "fred_series", symbol=series_id)
    if ingest:
        doc_id = _ingest_snapshot("fred_series", series_id, normalized)
        return {"doc_id": doc_id, "data": normalized}
    return {"data": normalized}


@router.post("/event")
async def ingest_event_timeline(payload: EventIngestRequest):
    """
    Ingest politics/regulatory/incident events into the timeline feed.
    """
    normalized = market_data_service.normalize_market_snapshot(payload.events, "event_timeline", symbol=payload.symbol)
    doc_id = _ingest_snapshot("event_timeline", payload.symbol, normalized)
    return {"doc_id": doc_id, "data": normalized}
