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
# Direct connection (5432) often fails in Vercel with [Errno 99] due to IPv6 issues.
if "supabase.co" in raw_url and ":5432" in raw_url:
    print("WARNING: Detected Supabase Direct URL (:5432). Auto-switching to Pooler (:6543) for Vercel compatibility.")
    DATABASE_URL = raw_url.replace(":5432", ":6543")
else:
    DATABASE_URL = raw_url

# Serverless-optimized engine configuration
# NullPool is recommended for serverless: creates new connection per request
# For connection pooling, Supabase's built-in PgBouncer can be used instead
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Disable SQL logging in production
    poolclass=NullPool,  # No connection pooling (serverless-friendly)
    # Supabase Pooler (PgBouncer) requires prepared statements to be disabled
    connect_args={
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
    },
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
