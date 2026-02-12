import { NextResponse, type NextRequest } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import {
  resolveBackendBaseUrl,
  resolvePrecisoRole,
  resolvePrecisoUserId,
} from "@/lib/preciso_proxy";

export const runtime = "nodejs";

function _tenantFromRequest(req: NextRequest): string {
  const cookieTenant = req.cookies.get("preciso_tenant_id")?.value;
  const headerTenant = req.headers.get("x-tenant-id") || req.headers.get("x-tenant") || "";
  const tenant = (cookieTenant || headerTenant || process.env.DEFAULT_TENANT_ID || "public").trim();
  return tenant || "public";
}

function _copyHeaders(req: NextRequest): Headers {
  const headers = new Headers();
  const accept = req.headers.get("accept");
  const contentType = req.headers.get("content-type");
  if (accept) headers.set("accept", accept);
  if (contentType) headers.set("content-type", contentType);
  return headers;
}

async function _proxy(req: NextRequest, params: { path: string[] }) {
  const session = await getServerSession(authOptions);
  const backend = resolveBackendBaseUrl();
  const path = "/" + params.path.join("/");
  const target = backend + path + (req.nextUrl.search || "");

  const headers = _copyHeaders(req);
  headers.set("x-tenant-id", _tenantFromRequest(req));
  headers.set("x-preciso-user-id", resolvePrecisoUserId(session));
  headers.set("x-preciso-user-role", resolvePrecisoRole(session));

  const adminToken = process.env.PRECISO_ADMIN_API_TOKEN;
  if (resolvePrecisoRole(session) === "admin" && adminToken) {
    headers.set("x-admin-token", adminToken);
  }

  const init: RequestInit = {
    method: req.method,
    headers,
    // NextRequest.body is a stream; pass through for non-GET/HEAD.
    body: req.method === "GET" || req.method === "HEAD" ? undefined : req.body,
    redirect: "manual",
    cache: "no-store",
  };

  const upstream = await fetch(target, init);
  const resHeaders = new Headers(upstream.headers);
  // Avoid leaking hop-by-hop headers.
  resHeaders.delete("connection");
  resHeaders.delete("keep-alive");
  resHeaders.delete("transfer-encoding");
  resHeaders.delete("upgrade");

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: resHeaders,
  });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return _proxy(req, await ctx.params);
}
export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return _proxy(req, await ctx.params);
}
export async function PUT(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return _proxy(req, await ctx.params);
}
export async function PATCH(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return _proxy(req, await ctx.params);
}
export async function DELETE(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return _proxy(req, await ctx.params);
}

