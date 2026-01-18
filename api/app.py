"""
FinDistill FastAPI Application for Vercel Serverless

Multi-format financial document distillation (v11.5 Strict):
- Ingestion: XBRL/XML (CY/PY), PDF, Excel, CSV
- Export: JSONL (CoT), Markdown, Parquet, HDF5
- Policy: 100% English-only, Poison Pill enabled
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, PlainTextResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text
import os
import json
import logging

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")

from .db import get_db, engine, Base
from .models import Document, ExtractedResult
from .services.ingestion import ingestion_service
from .services.normalizer import normalizer
from .services.exporter import exporter
from .services.embedder import embedder
from .auth_service import supabase_auth, get_current_user, require_auth
from .schemas import UserRegister, UserLogin, TokenResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    App lifespan context manager for startup/shutdown tasks.
    Perform database auto-migration on server startup.
    """
    try:
        logger.info("Starting database auto-migration...")
        async with engine.begin() as conn:
            # 1. Create vector extension if not exists
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("Vector extension checked/created.")
            
            # 2. Create all tables defined in models
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables checked/created successfully.")
            
            # 3. Add missing columns (safe migration for existing tables)
            try:
                await conn.execute(text("""
                    ALTER TABLE documents 
                    ADD COLUMN IF NOT EXISTS file_type VARCHAR
                """))
                logger.info("Column 'file_type' checked/added to documents table.")
            except Exception as col_error:
                logger.warning(f"Note: Could not add file_type column (may already exist): {col_error}")
            
            # 4. Migrate user_id from INTEGER to VARCHAR (for Supabase UUID)
            try:
                await conn.execute(text("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.table_constraints 
                            WHERE constraint_name = 'documents_user_id_fkey' 
                            AND table_name = 'documents'
                        ) THEN
                            ALTER TABLE documents DROP CONSTRAINT documents_user_id_fkey;
                        END IF;
                    END $$;
                """))
                logger.info("FK constraint 'documents_user_id_fkey' dropped (if existed).")
                
                result = await conn.execute(text("""
                    SELECT data_type FROM information_schema.columns 
                    WHERE table_name = 'documents' AND column_name = 'user_id'
                """))
                row = result.fetchone()
                
                if row and row[0] != 'character varying':
                    await conn.execute(text("""
                        ALTER TABLE documents 
                        ALTER COLUMN user_id TYPE VARCHAR(255) USING user_id::VARCHAR
                    """))
                    logger.info("Column 'user_id' migrated from INTEGER to VARCHAR.")
                else:
                    logger.info("Column 'user_id' is already VARCHAR type.")
                    
            except Exception as type_error:
                logger.error(f"ERROR during user_id migration: {type_error}", exc_info=True)
            
    except Exception as e:
        logger.critical(f"CRITICAL: Database initialization failed: {e}")
    
    yield
    
    await engine.dispose()


app = FastAPI(
    title="FinDistill API v11.5 (Strict English)",
    description="High-performance financial distillation with 100% English CoT data generation.",
    version="11.5.0",
    lifespan=lifespan
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request, call_next):
    """Log incoming requests to debug auth headers and paths."""
    logger.info(f"[API DEBUG] Request: {request.method} {request.url.path}")
    try:
        auth = request.headers.get("Authorization")
        if auth:
            logger.info(f"[API DEBUG] Auth Header present: {auth[:10]}...")
        else:
            logger.warning("[API DEBUG] No Authorization header found.")
        
        response = await call_next(request)
        return response
    except Exception as e:
        logger.critical(f"[API CRITICAL] Unhandled exception in request: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal Server Error: {str(e)}", "type": str(type(e).__name__)}
        )


@app.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint with DB verification."""
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "healthy", 
            "service": "FinDistill API", 
            "version": "2.1.1",
            "database": "connected"
        }
    except Exception as e:
        error_msg = str(e)
        from .db import DATABASE_URL
        masked_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "INVALID_URL"
        
        return {
            "status": "degraded", 
            "service": "FinDistill API", 
            "version": "2.0.0",
            "database": f"error: {error_msg}",
            "debug_info": {
                "dbal_host": masked_url
            }
        }


# ==================== AUTH ENDPOINTS ====================

@app.get("/api/debug-env")
async def debug_env():
    """
    Debug endpoint to check environment configuration safely.
    Values are masked for security.
    """
    settings = supabase_auth._get_settings()
    
    def mask(s):
        if not s: return "[EMPTY]"
        if len(s) < 10: return s[:2] + "***"
        return s[:5] + "***" + s[-5:]
    
    db_url = os.environ.get("SUPABASE_DATABASE_URL", "")
    
    return {
        "SB_URL": settings["url"],
        "SB_KEY_STATUS": "Present" if settings["anon_key"] else "Missing",
        "SB_KEY_MASKED": mask(settings["anon_key"]),
        "SB_JWT_STATUS": "Present" if settings["jwt_secret"] else "Missing",
        "DATABASE_URL_HAS_PARAMS": "?" in db_url,
        "DATABASE_URL_HAS_SB_KEY": "sb_key=" in db_url,
        "VERSION": "2.0.0-reset"
    }

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    return await supabase_auth.register(
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name
    )


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    return await supabase_auth.login(
        email=user_data.email,
        password=user_data.password
    )


@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(require_auth)):
    return {
        "id": current_user.get("id"),
        "email": current_user.get("email"),
        "role": current_user.get("role"),
        "metadata": current_user.get("user_metadata", {})
    }


@app.post("/api/extract")
async def extract_document(
    file: UploadFile = File(...),
    export_format: str = "jsonl",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """
    Extract and distill financial data from uploaded document.
    """
    try:
        user_id_str = current_user.get("sub")
        file_content = await fil
