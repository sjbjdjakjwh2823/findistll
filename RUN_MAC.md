# Run on macOS

This repo is designed to be reproducible without sharing secrets. Use `.env.example` as a template and create your local `.env` file.

## Requirements
- macOS 12+
- Python 3.12
- Node.js 22+

## One-time setup
```bash
cd /path/to/findistll

# Python + dependencies
bash scripts/setup_mac.sh

# Cloudflared (download per machine)
bash scripts/install_cloudflared_mac.sh
```

## Secrets
```bash
cp .env.example .env
# Fill in values in .env
```

## Run (local)
```bash
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

## Verify
```bash
curl http://localhost:8004/health
```

## Notes
- Cloudflared binary is stored at `bin/cloudflared` and is ignored by git.
- If you do not use Cloudflare tunnels, you can skip the install step.
