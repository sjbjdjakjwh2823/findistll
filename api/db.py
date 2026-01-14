"""
Supabase PostgreSQL Database Configuration for Vercel Serverless

Optimized connection pooling settings for serverless environments where
connections are frequently created and destroyed.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
import os

# Supabase PostgreSQL connection URL
# Supabase PostgreSQL connection URL
# Format: postgresql+asyncpg://user:password@host:port/database
raw_url = os.getenv(
    "SUPABASE_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/findistill_db")
)

# FIX: Force Supabase to use port 6543 (Transaction Pooler / IPv4)
if "supabase.co" in raw_url and ":5432" in raw_url:
    print("WARNING: Detected Supabase Direct URL (:5432). Auto-switching to Pooler (:6543) for Vercel compatibility.")
    DATABASE_URL = raw_url.replace(":5432", ":6543")
else:
    DATABASE_URL = raw_url

# FIX: Remove 'pgbouncer=true' query param if present (incompatible with asyncpg)
if "?" in DATABASE_URL and "pgbouncer=true" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")

# FIX: Resolve Hostname to IPv4 to prevent [Errno 99] (IPv6 mismatch) on Vercel
# and configure SSL to accept the IP-based connection (disable hostname check)
import socket
from urllib.parse import urlparse
import ssl

connect_args = {
    "prepared_statement_cache_size": 0,
    "statement_cache_size": 0,
}

try:
    if DATABASE_URL:
        DATABASE_URL = DATABASE_URL.strip()
        
    parsed = urlparse(DATABASE_URL)
    hostname = parsed.hostname
    
    # CASE 1: Supabase Pooler URLs (pooler.supabase.com)
    # SNI is required to route to the correct tenant - do NOT replace hostname with IP.
    # Explicitly enable SSL to ensure SNI is sent for tenant routing.
    if hostname and "pooler.supabase.com" in hostname:
        print(f"DEBUG: Using Supabase Pooler URL: {hostname}")
        # asyncpg needs explicit SSL config for proper SNI handling
        ssl_ctx = ssl.create_default_context()
        # Keep hostname verification disabled for flexibility (Supabase handles auth via SNI)
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx
        # CRITICAL: asyncpg needs server_hostname to send SNI correctly
        connect_args["server_hostname"] = hostname
        
    # CASE 2: Direct URLs (supabase.co)
    # Apply DNS resolution fix to prevent IPv6 issues on Vercel.
    elif hostname and "supabase.co" in hostname:
        # 1. Resolve to IPv4
        ip_address = socket.gethostbyname(hostname)
        print(f"DEBUG: Resolved {hostname} to {ip_address}")
        
        # 2. Replace hostname with IP in URL
        DATABASE_URL = DATABASE_URL.replace(hostname, ip_address)
        
        # 3. Create SSL Context that ignores hostname mismatch (since we are connecting to IP)
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE  # Supabase requires SSL, but we relax verification for IP connection
        
        connect_args["ssl"] = ssl_ctx
        
except Exception as e:
    print(f"WARNING: DNS Resolution fix failed: {e}")

# Serverless-optimized engine configuration
# NullPool is recommended for serverless: creates new connection per request
# For connection pooling, Supabase's built-in PgBouncer can be used instead
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Disable SQL logging in production
    poolclass=NullPool,  # No connection pooling (serverless-friendly)
    # Supabase Pooler (PgBouncer) requires prepared statements to be disabled
    # Supabase Pooler (PgBouncer) requires prepared statements to be disabled
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


async def get_db():
    """
    Async generator for database sessions.
    
    Usage with FastAPI Depends:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
