from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.db.registry import get_db
from app.services.spoke_c_rag import RAGEngine
from app.services.metrics_logger import MetricsLogger
from app.api.v1.generate import call_llm


router = APIRouter(prefix="/console", tags=["Console"])


class ModelRegistryIn(BaseModel):
    id: Optional[str] = None
    name: str
    provider: str = "openai"
    base_url: Optional[str] = None
    model: str
    purpose: str = "llm"
    is_default: bool = False
    metadata: Optional[Dict[str, Any]] = None


class LlmRunIn(BaseModel):
    prompt: str
    system_prompt: Optional[str] = "You are a financial analyst."
    model_id: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.4
    max_tokens: int = 1500
    metadata: Optional[Dict[str, Any]] = None


class RagRunIn(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    metadata_filter: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@router.get("/models")
def list_models(limit: int = 100, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    return {"models": db.list_model_registry(limit=limit)}


@router.post("/models")
def upsert_model(model: ModelRegistryIn, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    model_id = db.upsert_model_registry(model.model_dump())
    return {"model_id": model_id}


class DefaultModelIn(BaseModel):
    model_id: str


@router.post("/models/default")
def set_default_model(payload: DefaultModelIn, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    models = db.list_model_registry(limit=200)
    target = None
    for m in models:
        if m.get("id") == payload.model_id:
            target = m
            break
    if not target:
        raise HTTPException(status_code=404, detail="model not found")
    # unset all defaults
    for m in models:
        if m.get("id") == payload.model_id:
            continue
        m["is_default"] = False
        db.upsert_model_registry(m)
    target["is_default"] = True
    db.upsert_model_registry(target)
    return {"default_model_id": payload.model_id}


@router.get("/runs/llm")
def list_llm_runs(limit: int = 50, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    return {"runs": db.list_llm_runs(limit=limit)}


@router.get("/runs/rag")
def list_rag_runs(limit: int = 50, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    return {"runs": db.list_rag_runs(limit=limit)}


@router.post("/llm/run")
async def run_llm(payload: LlmRunIn, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    model_name = payload.model
    model_id = payload.model_id
    base_url = None
    if payload.model_id:
        models = db.list_model_registry(limit=50)
        for m in models:
            if m.get("id") == payload.model_id:
                model_name = m.get("model")
                base_url = m.get("base_url")
                break
    if not model_name:
        raise HTTPException(status_code=400, detail="Model is required")

    result = await call_llm(
        payload.system_prompt or "You are a financial analyst.",
        payload.prompt,
        model=model_name,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        base_url_override=base_url,
    )

    run_id = db.insert_llm_run(
        {
            "id": str(uuid4()),
            "user_id": user.user_id,
            "model_id": model_id,
            "model_name": model_name,
            "prompt": payload.prompt,
            "response": result.get("content"),
            "tokens": (result.get("token_usage") or {}).get("total_tokens"),
            "latency_ms": result.get("generation_time_ms"),
            "status": "completed",
            "metadata": payload.metadata or {},
        }
    )

    MetricsLogger().log("console.llm.run", 1, {"model": model_name, "user_id": user.user_id})
    return {"run_id": run_id, "result": result}


@router.post("/rag/query")
def run_rag(payload: RagRunIn, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    supa = getattr(db, "client", None)
    engine = RAGEngine(
        supabase_client=supa,
        db_client=db,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )
    context = engine.retrieve(
        query=payload.query,
        k=payload.top_k,
        threshold=payload.threshold,
        metadata_filter=payload.metadata_filter or {},
    )
    evidence = [
        {
            "chunk_id": r.chunk_id,
            "content": r.content,
            "similarity": r.similarity,
            "metadata": r.metadata,
        }
        for r in context.results
    ]

    run_id = db.insert_rag_run(
        {
            "id": str(uuid4()),
            "user_id": user.user_id,
            "query": payload.query,
            "response": {"evidence": evidence},
            "metrics": context.metrics,
            "status": "completed",
            "metadata": payload.metadata or {},
        }
    )
    db.insert_rag_run_chunks(run_id, evidence)

    MetricsLogger().log("console.rag.run", 1, {"user_id": user.user_id})
    return {
        "run_id": run_id,
        "query": payload.query,
        "evidence": evidence,
        "metrics": context.metrics,
    }
