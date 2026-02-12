from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.core.admin_auth import require_admin
from app.services.training_service import (
    enqueue_training_run,
    list_training_runs,
    get_auto_train_enabled,
    set_auto_train_enabled,
)


router = APIRouter(prefix="/training", tags=["Training"])


def _require_admin(
    user: CurrentUser = Depends(get_current_user),
    x_admin_token: Optional[str] = Header(default=None),
) -> CurrentUser:
    return require_admin(user, x_admin_token)


class TrainingRunRequest(BaseModel):
    dataset_version_id: str = Field(..., description="Dataset version to train")
    model_name: str = Field("preciso-default", description="Model name or local model id")
    local_model_path: Optional[str] = Field(default=None, description="Local model path for fine-tuning")
    training_args: Optional[Dict[str, Any]] = Field(default=None, description="Local training args (JSON)")
    notes: Optional[str] = Field(default=None)


@router.get("/runs")
def get_runs(limit: int = 200, _user: CurrentUser = Depends(_require_admin)):
    return list_training_runs(limit=limit)


@router.post("/run")
def run_training(req: TrainingRunRequest, user: CurrentUser = Depends(_require_admin)):
    return enqueue_training_run(
        dataset_version_id=req.dataset_version_id,
        model_name=req.model_name,
        local_model_path=req.local_model_path,
        training_args=req.training_args,
        triggered_by=user.user_id,
        auto=False,
        notes=req.notes,
    )


class AutoTrainRequest(BaseModel):
    enabled: bool = Field(..., description="Enable auto training on approval")


@router.get("/auto")
def get_auto_train(_user: CurrentUser = Depends(_require_admin)):
    return {"enabled": get_auto_train_enabled()}


@router.post("/auto")
def set_auto_train(req: AutoTrainRequest, _user: CurrentUser = Depends(_require_admin)):
    set_auto_train_enabled(req.enabled)
    return {"enabled": get_auto_train_enabled()}
