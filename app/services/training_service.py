from __future__ import annotations

import logging
import os
import subprocess
import threading
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.db.registry import get_db
from app.services.audit_logger import AuditLogger, AuditEntry
from app.services.enterprise_collab import EnterpriseCollabStore, TenantPipelineManager
from app.services.mlflow_service import MlflowService
from app.services.feature_flags import get_flag

logger = logging.getLogger(__name__)
_auto_train_override: Optional[bool] = None

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider() -> str:
    return (os.getenv("TRAINING_PROVIDER") or "none").strip().lower()


def get_auto_train_enabled() -> bool:
    if _auto_train_override is not None:
        return _auto_train_override
    return get_flag("auto_train_on_approval")


def set_auto_train_enabled(enabled: bool) -> None:
    global _auto_train_override
    _auto_train_override = bool(enabled)


def enqueue_training_run(
    *,
    dataset_version_id: str,
    model_name: str,
    local_model_path: Optional[str] = None,
    training_args: Optional[Dict[str, Any]] = None,
    triggered_by: str,
    auto: bool = False,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    db = get_db()
    provider = _provider()
    mlflow = MlflowService(db)
    pipeline_job_id: Optional[str] = None
    pipeline_store: Optional[EnterpriseCollabStore] = None
    try:
        manager = TenantPipelineManager(db)
        pipeline_store = manager.store
        job = manager.submit(
            user_id=triggered_by,
            job_type="train",
            flow="approval" if auto else "interactive",
            input_ref={
                "dataset_version_id": dataset_version_id,
                "model_name": model_name,
                "provider": provider,
            },
        )
        pipeline_job_id = str(job.get("id") or "")
    except Exception:
        pipeline_job_id = None

    mlflow_row = mlflow.start_run(
        dataset_version_id=dataset_version_id,
        model_name=model_name,
        params={
            "provider": provider,
            "local_model_path": local_model_path or "",
            "auto": auto,
            "training_args": training_args or {},
        },
        metrics={},
        artifacts=None,
        requested_by=triggered_by,
    )
    run = {
        "dataset_version_id": dataset_version_id,
        "model_name": model_name,
        "local_model_path": local_model_path,
        "training_args": training_args or {},
        "provider": provider,
        "status": "queued" if provider != "none" else "skipped",
        "auto": auto,
        "triggered_by": triggered_by,
        "created_at": _utc_now(),
        "notes": notes or "",
        "mlflow_run_id": mlflow_row.get("mlflow_run_id"),
        "pipeline_job_id": pipeline_job_id,
    }

    if provider == "none":
        if pipeline_job_id and pipeline_store is not None:
            try:
                pipeline_store.update_pipeline_job_status(
                    actor_user_id=triggered_by,
                    job_id=pipeline_job_id,
                    status="completed",
                    output_ref={"status": "skipped", "reason": "TRAINING_PROVIDER=none"},
                )
            except Exception:
                pass
    else:
        if pipeline_job_id and pipeline_store is not None:
            try:
                pipeline_store.update_pipeline_job_status(
                    actor_user_id=triggered_by,
                    job_id=pipeline_job_id,
                    status="pending",
                    output_ref={"status": "queued"},
                )
            except Exception:
                pass

    _maybe_run_local_training(run, pipeline_store=pipeline_store, pipeline_job_id=pipeline_job_id)
    try:
        AuditLogger(db).append_log(
            AuditEntry(
                action="training_run",
                actor_type="system" if auto else "user",
                actor_id=triggered_by,
                entity_type="dataset_version",
                entity_id=str(dataset_version_id),
                context=run,
                outcome={"ok": True},
            )
        )
    except Exception as exc:
        # Never block approval or admin actions if audit logging fails.
        logger.warning("Training audit log append failed: %s", exc)
    return run


def _maybe_run_local_training(
    run: Dict[str, Any],
    *,
    pipeline_store: Optional[EnterpriseCollabStore],
    pipeline_job_id: Optional[str],
) -> None:
    provider = (run.get("provider") or "").lower()
    if provider != "local":
        return
    command = (os.getenv("LOCAL_TRAINING_COMMAND") or "").strip()
    if not command:
        logger.warning("LOCAL_TRAINING_COMMAND not set; local training skipped.")
        run["status"] = "skipped"
        run["skip_reason"] = "missing_local_training_command"
        return

    def _launch() -> None:
        env = os.environ.copy()
        env.update(
            {
                "PRECISO_DATASET_VERSION_ID": str(run.get("dataset_version_id") or ""),
                "PRECISO_MODEL_NAME": str(run.get("model_name") or ""),
                "PRECISO_LOCAL_MODEL_PATH": str(run.get("local_model_path") or ""),
                "PRECISO_MLFLOW_RUN_ID": str(run.get("mlflow_run_id") or ""),
                "PRECISO_TRAINING_ARGS": json.dumps(run.get("training_args") or {}),
            }
        )
        try:
            proc = subprocess.Popen(command, shell=True, env=env)
            run["status"] = "running"
            if pipeline_store is not None and pipeline_job_id:
                try:
                    pipeline_store.update_pipeline_job_status(
                        actor_user_id=str(run.get("triggered_by") or "system"),
                        job_id=pipeline_job_id,
                        status="processing",
                        output_ref={"status": "running", "pid": proc.pid},
                    )
                except Exception:
                    pass
            exit_code = proc.wait()
            run["exit_code"] = int(exit_code)
            if exit_code == 0:
                run["status"] = "completed"
                if pipeline_store is not None and pipeline_job_id:
                    try:
                        pipeline_store.update_pipeline_job_status(
                            actor_user_id=str(run.get("triggered_by") or "system"),
                            job_id=pipeline_job_id,
                            status="completed",
                            output_ref={"status": "completed", "exit_code": int(exit_code)},
                        )
                    except Exception:
                        pass
            else:
                run["status"] = "failed"
                run["error"] = f"training exited with code {exit_code}"
                if pipeline_store is not None and pipeline_job_id:
                    try:
                        pipeline_store.update_pipeline_job_status(
                            actor_user_id=str(run.get("triggered_by") or "system"),
                            job_id=pipeline_job_id,
                            status="failed",
                            error=str(run.get("error") or ""),
                            output_ref={"status": "failed", "exit_code": int(exit_code)},
                        )
                    except Exception:
                        pass
        except Exception as exc:
            run["status"] = "failed"
            run["error"] = str(exc)
            logger.warning("Local training launch failed: %s", exc)
            if pipeline_store is not None and pipeline_job_id:
                try:
                    pipeline_store.update_pipeline_job_status(
                        actor_user_id=str(run.get("triggered_by") or "system"),
                        job_id=pipeline_job_id,
                        status="failed",
                        error=str(exc),
                    )
                except Exception:
                    pass

    threading.Thread(target=_launch, daemon=True).start()


def list_training_runs(limit: int = 200) -> Dict[str, Any]:
    db = get_db()
    try:
        rows = db.list_audit_logs(limit=limit)
    except Exception:
        rows = []
    items = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        if (r.get("action") or "") != "training_run":
            continue
        items.append(r.get("context") or {})
    return {"items": items}
