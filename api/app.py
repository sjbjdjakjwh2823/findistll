"""
FinDistill FastAPI Application for Vercel Serverless

Multi-format financial document distillation:
- Ingestion: PDF, Excel, CSV, Images
- Export: JSONL, Markdown, Parquet
- Database: Supabase with pgvector
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text
import os
import json

import google.generativeai as genai

from .db import get_db, engine, Base
from .models import Document, ExtractedResult
from .services.ingestion import ingestion_service
from .services.normalizer import normalizer
from .services.exporter import exporter
from .services.embedder import embedder

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    App lifespan context manager for startup/shutdown tasks.
    Perform database auto-migration on server startup.
    """
    try:
        # NOTE: Auto-migration disabled for Vercel stability.
        # Run migrations manually or via a separate script.
        pass
        # print("Starting database auto-migration...")
        # async with engine.begin() as conn:
        #     # 1. Create vector extension if not exists
        #     await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        #     print("Vector extension checked/created.")
        #     
        #     # 2. Create all tables defined in models
        #     # This is equivalent to "CREATE TABLE IF NOT EXISTS"
        #     await conn.run_sync(Base.metadata.create_all)
        #     print("Database tables checked/created successfully.")
            
    except Exception as e:
        print(f"CRITICAL: Database initialization failed: {e}")
        # We don't raise here to allow the app to start even if DB is flaky,
        # but errors will be logged for debugging.
    
    yield
    
    # Clean up connection resources on shutdown
    await engine.dispose()


app = FastAPI(
    title="FinDistill API",
    description="Financial Document Data Distillation API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for flexibility
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint with DB verification."""
    try:
        # Test DB connection
        await db.execute(text("SELECT 1"))
        return {
            "status": "healthy", 
            "service": "FinDistill API", 
            "version": "2.0.0",
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


@app.post("/api/extract")
async def extract_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Extract and distill financial data from uploaded document.
    
    Supports: PDF, Excel (.xlsx), CSV, Images (PNG, JPEG, WebP)
    """
    try:
        # 1. Read file
        file_content = await file.read()
        
        # 2. Process with ingestion service
        extracted_data = await ingestion_service.process_file(
            file_content,
            file.filename,
            file.content_type
        )
        
        # 3. Normalize financial data
        normalized_data = normalizer.normalize(extracted_data)
        
        # 4. Generate embedding for semantic search
        embed_text = embedder.create_document_text(normalized_data)
        embedding = await embedder.generate_embedding(embed_text)
        
        # 5. Save to Database
        doc = Document(
            filename=file.filename,
            file_path=f"memory://{file.filename}",
            file_type=file.content_type
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        
        # Save extraction result with embedding
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
            "available_exports": ["jsonl", "markdown", "parquet"]
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
async def get_history(db: AsyncSession = Depends(get_db)):
    """Get extraction history with export options."""
    stmt = (
        select(Document, ExtractedResult)
        .join(ExtractedResult, Document.id == ExtractedResult.document_id)
        .order_by(desc(Document.upload_date))
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    history = []
    for doc, res in rows:
        history.append({
            "id": doc.id,
            "filename": doc.filename,
            "file_type": getattr(doc, 'file_type', 'unknown'),
            "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
            "summary": res.data.get("summary", "No summary"),
            "title": res.data.get("title", "Untitled"),
            "exports": {
                "jsonl": f"/api/export/jsonl/{doc.id}",
                "markdown": f"/api/export/markdown/{doc.id}",
                "parquet": f"/api/export/parquet/{doc.id}"
            }
        })
    
    return history


@app.get("/api/document/{document_id}")
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed extraction result for a specific document."""
    stmt = (
        select(Document, ExtractedResult)
        .join(ExtractedResult, Document.id == ExtractedResult.document_id)
        .where(Document.id == document_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc, res = row
    return {
        "id": doc.id,
        "filename": doc.filename,
        "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
        "data": res.data,
        "exports": {
            "jsonl": f"/api/export/jsonl/{doc.id}",
            "markdown": f"/api/export/markdown/{doc.id}",
            "parquet": f"/api/export/parquet/{doc.id}"
        }
    }


# ==================== EXPORT ENDPOINTS ====================

@app.get("/api/export/jsonl/{document_id}")
async def export_jsonl(document_id: int, db: AsyncSession = Depends(get_db)):
    """
    Export document as JSONL format for LLM fine-tuning.
    Each line is an instruction-response pair.
    """
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
    """
    Export document as Markdown format for RAG systems.
    Hierarchical text with proper table formatting.
    """
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
    """
    Export document as Parquet format for analytics.
    Compressed columnar storage using PyArrow.
    """
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
        raise HTTPException(
            status_code=501,
            detail=f"Parquet export is not available in this environment: {str(e)}"
        )


async def _get_document_data(document_id: int, db: AsyncSession) -> dict:
    """Helper to fetch document data for export."""
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
    db: AsyncSession = Depends(get_db)
):
    """
    Semantic search across documents using vector similarity.
    Uses Gemini embeddings and pgvector.
    """
    from sqlalchemy import text
    
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
            "relevance_score": 1 - row[4]  # Convert distance to similarity
        }
        for row in rows
    ]
