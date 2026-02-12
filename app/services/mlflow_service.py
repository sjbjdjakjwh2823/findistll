from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import requests

from app.core.tenant_context import get_effective_tenant_id


class MlflowService:
    def __init__(self, db: Any) -> None:
        self.db = db
        self.tracking_uri = (os.getenv("MLFLOW_TRACKING_URI") or "").rstrip("/")

    def list_experiments(self) -> List[Dict[str, Any]]:
        if self.tracking_uri:
            try:
                r = requests.get(f"{self.tracking_uri}/api/2.0/mlflow/experiments/search", timeout=10)
                if r.ok:
                    return r.json().get("experiments") or []
            except Exception as exc:
                # Silent fallback is fine, but log for observability.
                import logging
                logging.getLogger(__name__).warning("MLflow experiments lookup failed", exc_info=exc)
        return [
            {
                "experiment_id": "local-default",
                "name": "preciso-default",
                "lifecycle_stage": "active",
                "artifact_location": "s3://preciso-mlflow/artifacts",
                "source": "stub",
            }
        ]

    def start_run(
        self,
        *,
        dataset_version_id: Optional[str],
        model_name: str,
        params: Dict[str, Any],
        metrics: Dict[str, Any],
        artifacts: Optional[Dict[str, Any]] = None,
        requested_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        tenant_id = get_effective_tenant_id()
        run_id = str(uuid4())
        status = "started"
        source = "stub"
        if self.tracking_uri:
            try:
                create_run = requests.post(
                    f"{self.tracking_uri}/api/2.0/mlflow/runs/create",
                    json={
                        "experiment_id": os.getenv("MLFLOW_EXPERIMENT_ID", "0"),
                        "run_name": f"preciso-{model_name}-{run_id[:8]}",
                        "tags": [
                            {"key": "tenant_id", "value": tenant_id},
                            {"key": "dataset_version_id", "value": dataset_version_id or ""},
                        ],
                    },
                    timeout=10,
                )
                if create_run.ok:
                    run_id = create_run.json().get("run", {}).get("info", {}).get("run_id", run_id)
                    source = "mlflow"
                for k, v in (params or {}).items():
                    requests.post(
                        f"{self.tracking_uri}/api/2.0/mlflow/runs/log-parameter",
                        json={"run_id": run_id, "key": str(k), "value": str(v)},
                        timeout=10,
                    )
                for k, v in (metrics or {}).items():
                    requests.post(
                        f"{self.tracking_uri}/api/2.0/mlflow/runs/log-metric",
                        json={"run_id": run_id, "key": str(k), "value": float(v), "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)},
                        timeout=10,
                    )
            except Exception:
                status = "started_local_fallback"

        row = {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "dataset_version_id": dataset_version_id,
            "mlflow_run_id": run_id,
            "model_name": model_name,
            "params": params or {},
            "metrics": metrics or {},
            "artifacts": artifacts or {},
            "requested_by": requested_by,
            "status": status,
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._insert_run_link(row)
        self._insert_lineage(
            {
                "tenant_id": tenant_id,
                "source_type": "dataset_version",
                "source_ref": dataset_version_id or "unknown",
                "target_type": "mlflow_run",
                "target_ref": run_id,
                "metadata": {"model_name": model_name, "status": status},
            }
        )
        return row

    def promote_model(
        self,
        *,
        model_name: str,
        version: str,
        stage: str,
        requested_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        source = "stub"
        if self.tracking_uri:
            try:
                requests.post(
                    f"{self.tracking_uri}/api/2.0/mlflow/model-versions/transition-stage",
                    json={
                        "name": model_name,
                        "version": version,
                        "stage": stage,
                        "archive_existing_versions": True,
                    },
                    timeout=10,
                )
                source = "mlflow"
            except Exception:
                source = "stub_fallback"
        return {
            "model_name": model_name,
            "version": version,
            "stage": stage,
            "source": source,
            "requested_by": requested_by,
            "promoted_at": datetime.now(timezone.utc).isoformat(),
        }

    def _insert_run_link(self, row: Dict[str, Any]) -> None:
        if hasattr(self.db, "client"):
            self.db.client.table("dataset_mlflow_links").insert(row).execute()
            return
        rows = getattr(self.db, "dataset_mlflow_links", None)
        if rows is None:
            rows = []
            setattr(self.db, "dataset_mlflow_links", rows)
        rows.append(row)

    def _insert_lineage(self, row: Dict[str, Any]) -> None:
        if hasattr(self.db, "client"):
            self.db.client.table("governance_lineage_events").insert(row).execute()
            return
        rows = getattr(self.db, "governance_lineage_events", None)
        if rows is None:
            rows = []
            setattr(self.db, "governance_lineage_events", rows)
        rows.append(row)
