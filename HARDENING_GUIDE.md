# 🐾 Preciso Hardening Guide: Apollo Tier (Sovereign Environment)

This guide defines security best practices for deploying Preciso in air-gapped or high-security institutional environments.

## 1. Container Hardening
- **Non-Root Execution**: Always run the container with a non-privileged user.
- **Minimal Base Image**: Use `python:3.11-slim` or `alpine` to reduce the attack surface.
- **Read-Only Root FS**: Mount the application directory as read-only where possible.

## 2. Network Isolation
- **Air-Gapped Sync**: Use `openclaw gateway sync` to move model weights and datasets via physical media if internet is unavailable.
- **Mutual TLS (mTLS)**: Enforce mTLS for all gRPC and HTTPS communication between the toolkit and client apps.

## 3. Cryptographic Integrity
- **ZKP Mandatory Mode**: Enable `DISTILL_FORCE_ZKP=1` to reject any data source that does not provide a valid Zero-Knowledge Proof.
- **Merkle-Chain Heartbeat**: The system will automatically shut down if the local Merkle Root does not match the signed state from the Master.

## 4. Hardware Security
- **HSM Integration**: Configure `AUDIT_VAULT_KEY_PATH` to point to a Hardware Security Module for signing audit logs.

---
*Preciso Apollo Tier v4.0 | 2026-02-03*
