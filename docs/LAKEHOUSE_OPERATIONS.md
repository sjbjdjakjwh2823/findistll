# Preciso Lakehouse Operations

## 목적
- Preciso OLTP(Supabase/Postgres)와 Lakehouse(Delta/Spark/MLflow/UC) 병행 운영 기준.

## 구성
- Docker: `docker-compose.onprem.yml` + `docker-compose.lakehouse.yml`
- K8s: `k8s/` + `k8s/lakehouse/`

## 필수 ENV
- `LAKEHOUSE_ENABLED=1`
- `DELTA_ROOT_URI=s3a://preciso-lakehouse`
- `MINIO_ENDPOINT=http://minio:9000`
- `SPARK_API_URL=http://spark-master:8080`
- `MLFLOW_TRACKING_URI=http://mlflow:5000`
- `UNITY_CATALOG_API_URL=http://unity-catalog-server:8085`

## API 점검
- `POST /api/v1/lakehouse/jobs/submit`
- `GET /api/v1/lakehouse/tables/{layer}/{table}/history`
- `POST /api/v1/lakehouse/tables/{layer}/{table}/time-travel-query`
- `GET /api/v1/mlflow/experiments`
- `POST /api/v1/mlflow/runs/start`
- `POST /api/v1/training/run` (local fine-tune: dataset_version_id + local model path)
- `POST /api/v1/governance/policies/apply`

## SQL 적용
- `supabase_all_in_one_safe.sql` 재실행 필요.

## SLO 권고
- RAG P95 < 1.5s
- lakehouse job enqueue latency < 500ms
- approval->mlflow candidate event < 30s
- local training start < 10s (export_only backend)
