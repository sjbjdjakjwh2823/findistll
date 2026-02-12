import os
from dataclasses import dataclass
from app.core.secret_loader import load_secrets_from_file


@dataclass(frozen=True)
class Settings:
    app_env: str
    db_backend: str
    database_url: str
    redis_url: str
    supabase_url: str
    supabase_service_role_key: str
    supabase_db_url: str
    hf_token: str
    hf_dataset: str
    cloudflare_tunnel_token: str
    public_domain: str
    default_tenant_id: str
    tenant_header_required: str
    rbac_enforced: str
    admin_api_token: str
    license_check_enabled: str
    license_key: str
    central_supabase_url: str
    supabase_anon_key: str
    opsgraph_autofill_enabled: str
    egress_mode: str
    egress_approval_required: str
    egress_sensitive_block: str
    lakehouse_enabled: str
    delta_root_uri: str
    minio_endpoint: str
    spark_api_url: str
    airflow_api_url: str
    mlflow_tracking_uri: str
    unity_catalog_api_url: str


def load_settings() -> Settings:
    load_secrets_from_file()
    return Settings(
        app_env=os.getenv("APP_ENV", "dev"),
        db_backend=os.getenv("DB_BACKEND", ""),
        database_url=os.getenv("DATABASE_URL", ""),
        redis_url=os.getenv("REDIS_URL", ""),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        supabase_db_url=os.getenv("SUPABASE_DB_URL", ""),
        hf_token=os.getenv("HF_TOKEN", ""),
        hf_dataset=os.getenv("HF_DATASET", ""),
        cloudflare_tunnel_token=os.getenv("CLOUDFLARE_TUNNEL_TOKEN", ""),
        public_domain=os.getenv("PUBLIC_DOMAIN", "preciso-data.com"),
        default_tenant_id=os.getenv("DEFAULT_TENANT_ID", "public"),
        tenant_header_required=os.getenv("TENANT_HEADER_REQUIRED", "0"),
        rbac_enforced=os.getenv("RBAC_ENFORCED", "0"),
        admin_api_token=os.getenv("ADMIN_API_TOKEN", ""),
        license_check_enabled=os.getenv("LICENSE_CHECK_ENABLED", "0"),
        license_key=os.getenv("LICENSE_KEY", ""),
        central_supabase_url=os.getenv("CENTRAL_SUPABASE_URL", ""),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        opsgraph_autofill_enabled=os.getenv("OPSGRAPH_AUTOFILL_ENABLED", "0"),
        egress_mode=os.getenv("EGRESS_MODE", "allow"),
        egress_approval_required=os.getenv("EGRESS_APPROVAL_REQUIRED", "0"),
        egress_sensitive_block=os.getenv("EGRESS_SENSITIVE_BLOCK", "1"),
        lakehouse_enabled=os.getenv("LAKEHOUSE_ENABLED", "0"),
        delta_root_uri=os.getenv("DELTA_ROOT_URI", "s3a://preciso-lakehouse"),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", ""),
        spark_api_url=os.getenv("SPARK_API_URL", ""),
        airflow_api_url=os.getenv("AIRFLOW_API_URL", ""),
        mlflow_tracking_uri=os.getenv("MLFLOW_TRACKING_URI", ""),
        unity_catalog_api_url=os.getenv("UNITY_CATALOG_API_URL", ""),
    )
