"""
FinDistill FastAPI Application for Vercel Serverless

This module contains the FastAPI app configured for Vercel deployment.
Files are processed in-memory (no local filesystem writes).
"""

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import os
import json
import io

import google.generativeai as genai

from .db import get_db
from .models import Document, ExtractedResult

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI(
    title="FinDistill API",
    description="Financial Document Data Extraction API",
    version="1.0.0"
)

# CORS Setup - Allow frontend domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://*.vercel.app",   # Vercel preview deployments
        # Add your production domain here
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "FinDistill API"}


@app.post("/api/extract")
async def extract_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Extract financial data from uploaded document.
    
    Processes PDF/image files using Gemini API and stores results in database.
    Files are processed in-memory for serverless compatibility.
    """
    try:
        # 1. Read file into memory (serverless: no local file system)
        file_content = await file.read()
        
        # 2. Upload to Gemini using bytes
        # Create a temporary file-like object for Gemini
        gemini_file = genai.upload_file(
            io.BytesIO(file_content),
            mime_type=file.content_type,
            display_name=file.filename
        )
        
        # 3. Extract Data with Gemini
        prompt = """
        Analyze this financial document. Extract the key financial data into a structured JSON format.
        The JSON should have the following structure:
        {
            "title": "Document Title",
            "summary": "Brief summary of the document",
            "tables": [
                {
                    "name": "Table Name",
                    "headers": ["Col1", "Col2"],
                    "rows": [["Val1", "Val2"]]
                }
            ],
            "key_metrics": {"metric": "value"}
        }
        """
        
        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config={"response_mime_type": "application/json"}
        )
        response = model.generate_content([gemini_file, prompt])
        extracted_data = response.text
        
        json_data = json.loads(extracted_data)
        
        # 4. Save to Database
        # Note: file_path is set to empty/placeholder since we don't store files locally
        doc = Document(
            filename=file.filename,
            file_path=f"memory://{file.filename}"  # Placeholder path
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        
        # Save extraction result
        result = ExtractedResult(
            document_id=doc.id,
            data=json_data,
            # embedding=embedding  # Add if needed
        )
        db.add(result)
        await db.commit()
        
        # Clean up Gemini file
        try:
            genai.delete_file(gemini_file.name)
        except Exception:
            pass  # Ignore cleanup errors
        
        return {"success": True, "document_id": doc.id, "data": json_data}

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
async def get_history(db: AsyncSession = Depends(get_db)):
    """
    Get extraction history.
    
    Returns list of all processed documents with their extraction summaries.
    """
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
            "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
            "summary": res.data.get("summary", "No summary"),
            "title": res.data.get("title", "Untitled")
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
        "data": res.data
    }
