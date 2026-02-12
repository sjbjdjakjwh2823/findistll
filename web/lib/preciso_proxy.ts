import type { Session } from "next-auth";

export type PrecisoRole = "auto" | "viewer" | "analyst" | "reviewer" | "approver" | "auditor" | "admin";

function parseCsvEnv(name: string): string[] {
  const raw = process.env[name] || "";
  return raw
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
}

export function resolvePrecisoRole(session: Session | null): PrecisoRole {
  const email = (session?.user?.email || "").toLowerCase();
  const admins = parseCsvEnv("PRECISO_ADMIN_EMAILS");
  if (email && admins.includes(email)) return "admin";
  // Let backend map role via org_users (tenant-scoped). Falls back to viewer.
  return session?.user?.email ? "auto" : "viewer";
}

export function resolvePrecisoUserId(session: Session | null): string {
  // Prefer DB user id; fallback to email (still stable).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const id = (session?.user as any)?.id as string | undefined;
  if (id) return id;
  return session?.user?.email || "anonymous";
}

export function resolveBackendBaseUrl(): string {
  const url =
    process.env.PRECISO_BACKEND_URL ||
    // Back-compat for existing setups; still used server-side only.
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";
  return url.replace(/\/+$/, "");
}
