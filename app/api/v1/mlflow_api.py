from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.db.registry import get_db
from app.services.mlflow_service import MlflowService


router = APIRouter(prefix="/mlflow", tags=["MLOps"])


class StartRunIn(BaseModel):
    dataset_version_id: Optional[str] = None
    model_name: str = Field(default="preciso-default")
    params: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, float] = Field(default_factory=dict)
    artifacts: Dict[str, Any] = Field(default_factory=dict)


class PromoteModelIn(BaseModel):
    version: str
    stage: str = Field(default="Staging")


@router.get("/experiments")
def list_experiments(user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    return {"experiments": MlflowService(db).list_experiments()}


@router.post("/runs/start")
def start_run(payload: StartRunIn, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    row = MlflowService(db).start_run(
        dataset_version_id=payload.dataset_version_id,
        model_name=payload.model_name,
        params=payload.params,
        metrics=payload.metrics,
        artifacts=payload.artifacts,
        requested_by=user.user_id,
    )
    return {"run": row}


@router.post("/models/{name}/promote")
def promote_model(name: str, payload: PromoteModelIn, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    res = MlflowService(db).promote_model(
        model_name=name,
        version=payload.version,
        stage=payload.stage,
        requested_by=user.user_id,
    )
    return {"promotion": res}
