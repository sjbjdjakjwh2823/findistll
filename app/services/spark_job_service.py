from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

import requests

from app.core.tenant_context import get_effective_tenant_id


class SparkJobService:
    def __init__(self, db: Any) -> None:
        self.db = db
        self.airflow_api_url = (os.getenv("AIRFLOW_API_URL") or "").rstrip("/")
        self.airflow_dag_id = os.getenv("AIRFLOW_LAKEHOUSE_DAG_ID", "preciso_lakehouse_pipeline")
        self.spark_api_url = (os.getenv("SPARK_API_URL") or "").rstrip("/")

    def submit(
        self,
        *,
        job_type: str,
        payload: Dict[str, Any],
        priority: str = "normal",
        requested_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        tenant_id = get_effective_tenant_id()
        job_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        status = "queued"
        dispatch = "local"

        if self.airflow_api_url:
            dispatch = "airflow"
            try:
                requests.post(
                    f"{self.airflow_api_url}/api/v1/dags/{self.airflow_dag_id}/dagRuns",
                    json={
                        "dag_run_id": f"preciso-{job_id}",
                        "conf": {
                            "job_id": job_id,
                            "job_type": job_type,
                            "tenant_id": tenant_id,
                            "payload": payload,
                        },
                    },
                    timeout=10,
                )
            except Exception:
                status = "queued_local"
                dispatch = "local_fallback"
        elif self.spark_api_url:
            dispatch = "spark_api"
            try:
                requests.post(
                    f"{self.spark_api_url}/v1/jobs/submit",
                    json={
                        "job_id": job_id,
                        "job_type": job_type,
                        "tenant_id": tenant_id,
                        "payload": payload,
                    },
                    timeout=10,
                )
            except Exception:
                status = "queued_local"
                dispatch = "local_fallback"

        row = {
            "id": job_id,
            "tenant_id": tenant_id,
            "job_type": job_type,
            "priority": priority,
            "status": status,
            "payload": payload,
            "dispatch_backend": dispatch,
            "requested_by": requested_by,
            "created_at": now,
            "updated_at": now,
        }
        self._insert_job(row)
        self._insert_lineage(
            {
                "tenant_id": tenant_id,
                "source_type": "job",
                "source_ref": job_type,
                "target_type": "delta_table",
                "target_ref": str((payload or {}).get("table") or "unknown"),
                "metadata": {"job_id": job_id, "payload": payload},
            }
        )
        return row

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        if hasattr(self.db, "client"):
            res = self.db.client.table("lakehouse_jobs").select("*").eq("id", job_id).limit(1).execute()
            return (res.data or [None])[0]
        rows = getattr(self.db, "lakehouse_jobs", []) or []
        for row in rows:
            if row.get("id") == job_id and row.get("tenant_id") == get_effective_tenant_id():
                return row
        return None

    def _insert_job(self, row: Dict[str, Any]) -> None:
        if hasattr(self.db, "client"):
            self.db.client.table("lakehouse_jobs").insert(row).execute()
            return
        rows = getattr(self.db, "lakehouse_jobs", None)
        if rows is None:
            rows = []
            setattr(self.db, "lakehouse_jobs", rows)
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
