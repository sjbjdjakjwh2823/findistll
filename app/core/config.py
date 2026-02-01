import os
from dataclasses import dataclass
from app.core.secret_loader import load_secrets_from_file


@dataclass(frozen=True)
class Settings:
    app_env: str
    supabase_url: str
    supabase_service_role_key: str
    supabase_db_url: str
    hf_token: str
    hf_dataset: str
    cloudflare_tunnel_token: str
    public_domain: str


def load_settings() -> Settings:
    load_secrets_from_file()
    return Settings(
        app_env=os.getenv("APP_ENV", "dev"),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        supabase_db_url=os.getenv("SUPABASE_DB_URL", ""),
        hf_token=os.getenv("HF_TOKEN", ""),
        hf_dataset=os.getenv("HF_DATASET", ""),
        cloudflare_tunnel_token=os.getenv("CLOUDFLARE_TUNNEL_TOKEN", ""),
        public_domain=os.getenv("PUBLIC_DOMAIN", "preciso-data.com"),
    )
