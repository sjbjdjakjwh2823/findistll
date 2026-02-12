# Preciso B2B SDK: Unified Authentication (Auth) Module Documentation

## 1. Overview
The Preciso B2B SDK Auth module provides a Palantir-class, sovereign authentication and authorization system for institutional clients. It ensures that sensitive financial intelligence remains secure while providing flexible integration for B2B partners.

## 2. Authentication Architecture
The system uses a multi-layered authentication approach:

### A. API Key Authentication (Partner Secret)
- **Use Case**: Direct server-to-server (S2S) integration.
- **Mechanism**: Partners are issued a unique `PRE_PARTNER_ID` and `PRE_PARTNER_SECRET`.
- **Header**: `X-Preciso-API-Key: <SECRET>`

### B. OAuth2 Integration (Federated Identity)
- **Providers**: Google (Workspace), GitHub (Enterprise).
- **Use Case**: End-user access to the Preciso Dashboard.
- **Client IDs**:
  - Google: `603455779355-6hilijrmdobqqjt2h45l1lrq2dsmn0j6.apps.googleusercontent.com`
  - GitHub: `ecfaaaa12ba2c1121c144f925923c2a05ac392e5`

### C. ZKP-Based Token Verification (Advanced)
- **Concept**: Zero-Knowledge Proof based verification for on-premise deployments where the partner does not want to share raw user IDs with the central Preciso server.

## 3. RBAC (Role-Based Access Control)
Roles are enforced at the API Gateway level (FastAPI + Supabase Auth):

| Role | Access Level | Description |
|------|--------------|-------------|
| **Admin** | Full Access | Manage API keys, datasets, and global configurations. |
| **Analyst** | Write/Read | Run distillations, create cases, and generate decision reports. |
| **Auditor** | Read-Only | View immutable audit logs and evidence chains. |
| **Guest** | Limited Read | View shared public dashboards and high-level metrics. |

## 4. Security Protocols
- **Encryption**: TLS 1.3 for data in transit. AES-256 for sensitive payload storage in Supabase.
- **Audit Logging**: Every authentication event and API call is logged to the `audit_events` table for compliance.
- **Rate Limiting**: Tiered rate limiting based on Partner ID (100-1000 req/min).

## 5. SDK Integration Example (Python)
```python
from preciso_sdk import PrecisoClient

# Initialize with B2B Credentials
client = PrecisoClient(
    partner_id="PARTNER_123",
    api_key="sk_live_..."
)

# Authenticated Session
session = client.auth.login_oauth("google")
```

## 6. Review Checklist
- [x] Multi-tenant isolation verified in Supabase RLS.
- [x] API Key rotation mechanism implemented.
- [x] ZKP proof verification logic aligned with Phase 5.5 roadmap.
- [x] OAuth2 redirect URIs configured for `preciso-data.com`.
