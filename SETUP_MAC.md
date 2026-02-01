# Mac Setup (Reproducible)

This setup avoids sharing secrets. You will add your own `.env`/keys locally.

## Requirements
- macOS 12+
- Python 3.12
- Node.js 22+

## One-time setup
```bash
cd /path/to/findistll

# Python + dependencies
bash scripts/setup_mac.sh

# Cloudflared binary (downloaded per-machine)
bash scripts/install_cloudflared_mac.sh
```

## Secrets
- Do **not** commit secrets.
- Create local `.env` (or whatever your deployment expects) on each machine.

## Verify
```bash
./bin/cloudflared --version
python -V
node -v
```
