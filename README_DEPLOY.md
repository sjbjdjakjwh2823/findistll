# Preciso Deploy (Concise)

## Purpose
Short checklist for deploying this repo without exposing internal details.

## Basic flow
1. Ensure the target server is reachable and you have SSH access.
2. Run the deploy script from the repo root.
3. Verify the service health endpoint and UI load.

## Scripts
- `deploy-to-oracle.ps1` (Windows)
- `deploy_oracle.sh` (Linux/macOS)
- `deploy_autofix.sh` (repair helper)

## Verify
- Service status (systemd or process manager)
- Health endpoint responds
- UI loads without console errors

## Notes
Keep secrets out of Git. Use `.env` locally and `.env.example` for templates.
