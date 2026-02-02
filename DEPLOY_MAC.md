# macOS Deploy Guide

This is a macOS-friendly deployment guide that avoids sharing secrets in git.

## Requirements
- macOS 12+
- Python 3.12
- Node.js 22+
- Cloudflare account (if using tunnels)

## One-time setup
```bash
cd /path/to/findistll
bash scripts/setup_mac.sh
bash scripts/install_cloudflared_mac.sh
```

## Secrets
```bash
cp .env.example .env
# Fill in values in .env
```

## Run locally (sanity check)
```bash
bash scripts/run_mac.sh
```

## Cloudflare tunnel (optional)
```bash
./bin/cloudflared --version
# Create and configure tunnels in Cloudflare dashboard
# Use your CLOUDFLARE_TUNNEL_TOKEN in .env
```

## Server deploy (Oracle Ubuntu example)
If deploying to an Ubuntu server, use the existing Oracle docs and scripts:
- `ORACLE_SETUP.md`
- `ORACLE_DEPLOY_GUIDE.md`
- `deploy_oracle.sh`

## Verify
```bash
curl http://localhost:8004/health
```
