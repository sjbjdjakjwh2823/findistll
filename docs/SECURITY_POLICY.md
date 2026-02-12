# Security Policy (Preciso)

## RBAC
- Default role: `viewer`
- Admin bypass allowed only for emergency

## Tenant Isolation
- Require `X-Tenant-Id` header in production
- Deny cross-tenant reads/writes

## Secrets
- Use a single secret source for runtime
- No secrets in repo
