from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import shutil
import os
from pathlib import Path
from typing import List

from .core.db import get_db
from .models.base import Document, ExtractedResult
from .services.ai_service import ai_service
from .models.document import Document
from .models.extracted_result import ExtractedResult

app = FastAPI(title="FinDistill API")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.on_event("startup")
async def on_startup():
    # Ensure tables exist (redundant if init_db script is run, but good for dev)
    # await init_db()
    pass

@app.post("/api/extract")
async def extract_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        # 1. Save File Locally
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Process with Gemini
        # We need to prepare data for Gemini (assuming image or pdf)
        # For simplicity, we assume we pass the file path or bytes to a helper that converts to Gemini friendly format
        # Gemini Python SDK supports 'upload_file' or passing bytes for images.
        # Since ai_service expects 'image_parts', let's adjust it to handle file upload or raw data.
        # Quick fix: Use the file path with genai.upload_file in the service, but here we'll read bytes for simplicity if it's an image
        
        import google.generativeai as genai
        
        # Upload to Gemini (File API is robust for PDFs)
        gemini_file = genai.upload_file(path=str(file_path), display_name=file.filename)
        
        # 3. Extract Data
        # We pass the file reference to our service
        # Updating service call pattern on the fly to match robust file handling
        
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
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
        response = model.generate_content([gemini_file, prompt])
        extracted_data = response.text # Should be JSON string
        
        import json
        json_data = json.loads(extracted_data)
        
        # 4. Save to DB
        # Save Document
        doc = Document(filename=file.filename, file_path=str(file_path))
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        
        # Save Result
        # Gen embedding (summary)
        summary = json_data.get("summary", "")
        # embedding = await ai_service.generate_embedding(summary) # Optional: enable if embedding needed
        
        result = ExtractedResult(
            document_id=doc.id, 
            data=json_data,
            # embedding=embedding # Add if needed and vector extension ready
        )
        db.add(result)
        await db.commit()
        
        return {"success": True, "document_id": doc.id, "data": json_data}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
async def get_history(db: AsyncSession = Depends(get_db)):
    # Join Document and ExtractedResult
    stmt = select(Document, ExtractedResult).join(ExtractedResult, Document.id == ExtractedResult.document_id).order_by(desc(Document.upload_date))
    result = await db.execute(stmt)
    rows = result.all()
    
    history = []
    for doc, res in rows:
        history.append({
            "id": doc.id,
            "filename": doc.filename,
            "upload_date": doc.upload_date,
            "summary": res.data.get("summary", "No summary"),
            "title": res.data.get("title", "Untitled")
        })
    return history
