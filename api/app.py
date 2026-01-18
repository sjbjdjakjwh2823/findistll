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
        file_content = await file.read()
        
        extracted_data = await ingestion_service.process_file(
            file_content,
            file.filename,
            file.content_type
        )
        
        normalized_data = normalizer.normalize(extracted_data)
        embed_text = embedder.create_document_text(normalized_data)
        embedding = await embedder.generate_embedding(embed_text)
        
        doc = Document(
            filename=file.filename,
            file_path=f"memory://{file.filename}",
            file_type=file.content_type,
            user_id=user_id_str
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        
        result = ExtractedResult(
            document_id=doc.id,
            data=normalized_data,
            embedding=embedding
        )
        db.add(result)
        await db.commit()
        
        return {
            "success": True,
            "document_id": doc.id,
            "data": normalized_data,
            "available_exports": ["jsonl", "markdown", "parquet", "hdf5"]
        }

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
async def get_history(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    user_id = current_user.get("sub")
    
    stmt = (
        select(Document, ExtractedResult)
        .join(ExtractedResult, Document.id == ExtractedResult.document_id)
        .where(Document.user_id == user_id)
        .order_by(desc(Document.upload_date))
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    history = []
    for doc, res in rows:
        history.append({
            "id": doc.id,
            "filename": doc.filename,
            "file_type": getattr(doc, "file_type", "unknown"),
            "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
            "summary": res.data.get("summary", "No summary"),
            "title": res.data.get("title", "Untitled"),
            "exports": {
                "jsonl": f"/api/export/jsonl/{doc.id}",
                "markdown": f"/api/export/markdown/{doc.id}",
                "parquet": f"/api/export/parquet/{doc.id}",
                "hdf5": f"/api/export/hdf5/{doc.id}"
            }
        })
    
    return history


@app.get("/api/document/{document_id}")
async def get_document(
    document_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    user_id = current_user.get("sub")
    
    stmt = (
        select(Document, ExtractedResult)
        .join(ExtractedResult, Document.id == ExtractedResult.document_id)
        .where(Document.id == document_id)
        .where(Document.user_id == user_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Document not found or access denied")
    
    doc, res = row
    return {
        "id": doc.id,
        "filename": doc.filename,
        "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
        "data": res.data,
        "exports": {
            "jsonl": f"/api/export/jsonl/{doc.id}",
            "markdown": f"/api/export/markdown/{doc.id}",
            "parquet": f"/api/export/parquet/{doc.id}",
            "hdf5": f"/api/export/hdf5/{doc.id}"
        }
    }


# ==================== EXPORT ENDPOINTS ====================

@app.get("/api/export/jsonl/{document_id}")
async def export_jsonl(document_id: int, db: AsyncSession = Depends(get_db)):
    data = await _get_document_data(document_id, db)
    jsonl_content = exporter.to_jsonl(data)
    
    return PlainTextResponse(
        content=jsonl_content,
        media_type="application/jsonl",
        headers={
            "Content-Disposition": f"attachment; filename=document_{document_id}.jsonl"
        }
    )


@app.get("/api/export/markdown/{document_id}")
async def export_markdown(document_id: int, db: AsyncSession = Depends(get_db)):
    data = await _get_document_data(document_id, db)
    markdown_content = exporter.to_markdown(data)
    
    return PlainTextResponse(
        content=markdown_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename=document_{document_id}.md"
        }
    )


@app.get("/api/export/parquet/{document_id}")
async def export_parquet(document_id: int, db: AsyncSession = Depends(get_db)):
    data = await _get_document_data(document_id, db)
    try:
        parquet_content = exporter.to_parquet(data)
        return Response(
            content=parquet_content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename=document_{document_id}.parquet"
            }
        )
    except (ImportError, RuntimeError) as e:
        raise HTTPException(status_code=501, detail=f"Parquet export error: {str(e)}")


@app.get("/api/export/hdf5/{document_id}")
async def export_hdf5(document_id: int, db: AsyncSession = Depends(get_db)):
    data = await _get_document_data(document_id, db)
    try:
        hdf5_content = exporter.to_hdf5(data)
        return Response(
            content=hdf5_content,
            media_type="application/x-hdf5",
            headers={
                "Content-Disposition": f"attachment; filename=document_{document_id}.h5"
            }
        )
    except (ImportError, RuntimeError) as e:
        raise HTTPException(status_code=501, detail=f"HDF5 export error: {str(e)}")


async def _get_document_data(document_id: int, db: AsyncSession) -> dict:
    stmt = (
        select(ExtractedResult)
        .where(ExtractedResult.document_id == document_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return row[0].data


# ==================== SEARCH ENDPOINT ====================

@app.get("/api/search")
async def semantic_search(
    query: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    # Generate query embedding
    query_embedding = await embedder.generate_query_embedding(query)
    
    # Vector similarity search
    sql = text("""
        SELECT 
            d.id, d.filename, d.upload_date,
            er.data,
            er.embedding <-> :query_vec AS distance
        FROM documents d
        JOIN extracted_results er ON d.id = er.document_id
        WHERE er.embedding IS NOT NULL
        ORDER BY er.embedding <-> :query_vec
        LIMIT :limit
    """)
    
    result = await db.execute(sql, {
        "query_vec": str(query_embedding),
        "limit": limit
    })
    rows = result.fetchall()
    
    return [
        {
            "id": row[0],
            "filename": row[1],
            "upload_date": row[2].isoformat() if row[2] else None,
            "title": row[3].get("title", "Untitled"),
            "summary": row[3].get("summary", ""),
            "relevance_score": 1 - row[4]
        }
        for row in rows
    ]
