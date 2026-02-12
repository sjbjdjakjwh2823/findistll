from __future__ import annotations

import os
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.core.admin_auth import require_admin
from app.db.supabase_rest_client import create_client as create_supabase_rest_client


router = APIRouter(prefix="/admin/connectivity", tags=["Admin - Connectivity"])
logger = logging.getLogger(__name__)


def _require_admin(
    user: CurrentUser = Depends(get_current_user),
    x_admin_token: Optional[str] = Header(default=None),
) -> CurrentUser:
    return require_admin(user, x_admin_token)


class ConnectivityRequest(BaseModel):
    supabase_url: Optional[str] = Field(default=None)
    supabase_service_role_key: Optional[str] = Field(default=None)
    db_url: Optional[str] = Field(default=None)
    redis_url: Optional[str] = Field(default=None)
    http_url: Optional[str] = Field(default=None)


def _check_supabase(url: Optional[str], key: Optional[str]) -> dict:
    if not url or not key:
        return {"ok": False, "error": "missing supabase url or service role key"}
    try:
        client = create_supabase_rest_client(url, key)
        client.table("cases").select("*").limit(1).execute()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_postgres(db_url: Optional[str]) -> dict:
    if not db_url:
        return {"ok": False, "error": "missing db_url"}
    try:
        import psycopg2  # type: ignore

        conn = psycopg2.connect(db_url, connect_timeout=5)
        conn.close()
        return {"ok": True, "driver": "psycopg2"}
    except Exception as exc:
        logger.warning("psycopg2 connectivity failed, trying asyncpg", exc_info=exc)

    try:
        import asyncpg  # type: ignore

        import asyncio

        async def _run() -> None:
            conn = await asyncpg.connect(db_url, timeout=5)
            await conn.close()

        asyncio.run(_run())
        return {"ok": True, "driver": "asyncpg"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_redis(redis_url: Optional[str]) -> dict:
    if not redis_url:
        return {"ok": False, "error": "missing redis_url"}
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(redis_url)
        client.ping()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_http(url: Optional[str]) -> dict:
    if not url:
        return {"ok": False, "error": "missing http_url"}
    try:
        import httpx  # type: ignore

        with httpx.Client(timeout=5) as client:
            r = client.get(url)
            return {"ok": r.status_code < 500, "status_code": r.status_code}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/validate")
async def validate_connectivity(
    payload: ConnectivityRequest,
    _user: CurrentUser = Depends(_require_admin),
):
    supa = _check_supabase(payload.supabase_url, payload.supabase_service_role_key)
    pg = _check_postgres(payload.db_url)
    red = _check_redis(payload.redis_url)
    http = _check_http(payload.http_url)
    return {
        "supabase": supa,
        "postgres": pg,
        "redis": red,
        "http": http,
    }
