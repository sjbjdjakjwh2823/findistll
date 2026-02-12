from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import load_settings
from app.db.supabase_db import SupabaseDB
from app.services.distill_engine import FinDistillAdapter
from app.services.multi_agent_framework import MultiAgentOrchestrator
from app.services.robot_engine import FinRobotAdapter

router = APIRouter(prefix="/multi-agent", tags=["Multi-Agent"])


class MultiAgentRunRequest(BaseModel):
    case_id: str
    document: Dict[str, Any]


@router.post("/run")
async def run_multi_agent(payload: MultiAgentRunRequest):
    settings = load_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    db = SupabaseDB(settings.supabase_url, settings.supabase_service_role_key)
    orchestrator = MultiAgentOrchestrator(db=db, distill=FinDistillAdapter(), robot=FinRobotAdapter())
    return await orchestrator.run(payload.case_id, payload.document)
