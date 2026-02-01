import os


SECRET_PATH = r"C:\Users\Administrator\Desktop\중요.txt"


def load_secrets_from_file() -> None:
    if not os.path.exists(SECRET_PATH):
        return

    try:
        with open(SECRET_PATH, "r", encoding="utf-8") as f:
            content = f.read().splitlines()
    except Exception:
        return

    for line in content:
        if "허깅페이스 토큰" in line:
            _set_env_from_line(line, "HF_TOKEN")
        elif line.lower().startswith("datasets"):
            _set_env_from_line(line, "HF_DATASET")
        elif line.lower().startswith("supabase url"):
            _set_env_from_line(line, "SUPABASE_URL")
        elif line.lower().startswith("supabase service_role"):
            _set_env_from_line(line, "SUPABASE_SERVICE_ROLE_KEY")
        elif line.lower().startswith("supabase db url"):
            _set_env_from_line(line, "SUPABASE_DB_URL")
        elif line.lower().startswith("cloudflare tunnel token"):
            _set_env_from_line(line, "CLOUDFLARE_TUNNEL_TOKEN")
        elif line.lower().startswith("fred api"):
            _set_env_from_line(line, "FRED_API_KEY")
        elif line.lower().startswith("openai api key"):
            _set_env_from_line(line, "OPENAI_API_KEY")
        elif line.lower().startswith("finnhub api key"):
            _set_env_from_line(line, "FINNHUB_API_KEY")
        elif line.lower().startswith("fmp api key"):
            _set_env_from_line(line, "FMP_API_KEY")
        elif line.lower().startswith("sec api key"):
            _set_env_from_line(line, "SEC_API_KEY")


def _set_env_from_line(line: str, key: str) -> None:
    if os.getenv(key):
        return
    parts = line.split(":", 1)
    if len(parts) != 2:
        return
    value = parts[1].strip()
    if value:
        os.environ[key] = value
