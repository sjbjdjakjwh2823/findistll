from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="preciso_lakehouse_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["preciso", "lakehouse"],
) as dag:
    run_pipeline = BashOperator(
        task_id="run_lakehouse_pipeline",
        bash_command="python /opt/airflow/dags/lakehouse_pipeline.py",
    )

    run_pipeline
