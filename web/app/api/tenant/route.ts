import { NextResponse, type NextRequest } from "next/server";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => ({}))) as { tenant_id?: string };
  const tenant = String(body.tenant_id || "").trim();
  if (!tenant) {
    return NextResponse.json({ ok: false, error: "tenant_id required" }, { status: 400 });
  }
  const res = NextResponse.json({ ok: true, tenant_id: tenant });
  res.cookies.set("preciso_tenant_id", tenant, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  });
  return res;
}

