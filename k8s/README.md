# Preciso Kubernetes (Prepared, Not Active)

This folder provides a **future Kubernetes** deployment layout that mirrors the on‑prem Docker Compose setup.
It intentionally omits secrets; inject those via Kubernetes Secrets or external secret managers.

## Files
- `namespace.yaml`: Optional namespace for isolation.
- `configmap.yaml`: Non‑secret env defaults.
- `secrets.example.yaml`: Example secret keys (fill in values or replace with external secret manager).
- `backend-deployment.yaml`: FastAPI backend.
- `worker-deployment.yaml`: Background worker.
- `redis-deployment.yaml`: Redis (use managed Redis in production if possible).
- `service-backend.yaml`: Backend service.
- `service-redis.yaml`: Redis service.
- `ingress.yaml`: Ingress template (domain + TLS).
- `kustomization.yaml`: Kustomize bundle.
- `lakehouse/*`: MinIO/Spark/MLflow/Unity Catalog baseline manifests.

## Apply (when ready)
```
kubectl apply -k k8s
```

Lakehouse-only apply:
```
kubectl apply -k k8s/lakehouse
```

## Notes
- Replace images (`IMAGE_BACKEND`, `IMAGE_WORKER`) with your registry.
- Set secrets in `secrets.yaml` or via external secret manager (recommended).
- For production, use managed Postgres and Redis; point env vars accordingly.
