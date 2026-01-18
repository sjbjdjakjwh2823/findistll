"""
FinDistill File Ingestion Service

Handles parsing of various file formats using Gemini API via HTTP.

[Input Formats - Optimized Processing]
- PDF (.pdf): Gemini multimodal for complex table extraction
- Images (.jpg, .png, .tiff, .webp, .heic): Gemini OCR + structure understanding
- Word (.docx): python-docx for text extraction + Gemini for summarization
- HWP (.hwpx): XML extraction + Gemini for summarization  
- Excel (.xlsx, .xls): openpyxl for structured data + Gemini for summary
- CSV (.csv): Python csv module + Gemini for summary

[Output Formats]
- JSONL: For LLM fine-tuning (instruction-response pairs)
- Markdown: For RAG systems (preserves document hierarchy)
"""

import io
import json
import csv
import base64
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
import os
import logging
import copy
import httpx

# Standard imports assuming requirements.txt is satisfied
import docx

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini API configuration
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiClient:
    """Simple Gemini API client using httpx."""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model = "gemini-2.0-flash"
        
    async def generate_content(self, contents: list, response_mime_type: str = None) -> str:
        """Generate content using Gemini API."""
        url = f"{GEMINI_API_BASE}/models/{self.model}:generateContent?key={self.api_key}"
        
        generation_config = {}
        if response_mime_type:
            generation_config["responseMimeType"] = response_mime_type
        
        payload = {"contents": contents}
        if generation_config:
            payload["generationConfig"] = generation_config
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
        # Extract text from response
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return ""
    
    async def generate_with_file(self, file_content: bytes, mime_type: str, prompt: str, response_mime_type: str = None) -> str:
        """Generate content with inline file data."""
        # Encode file as base64
        file_b64 = base64.b64encode(file_content).decode("utf-8")
        
        contents = [{
            "parts": [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": file_b64
                    }
                },
                {"text": prompt}
            ]
        }]
        
        return await self.generate_content(contents, response_mime_type)


class FileIngestionService:
    """Service for ingesting and parsing various file formats."""
    
    # Comprehensive file format support
    SUPPORTED_FORMATS = {
        # PDF - Gemini multimodal for complex layout
        'application/pdf': 'pdf',
        
        # Images - Gemini OCR and structure recognition
        'image/png': 'image',
        'image/jpeg': 'image',
        'image/tiff': 'image',
        'image/webp': 'image',
        'image/heic': 'image',
        
        # Word documents - python-docx extraction
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        
        # HWP (Korean word processor) - XML extraction from HWPX
        'application/hwp+zip': 'hwpx',
        'application/x-hwpx': 'hwpx',
        
        # Excel - openpyxl for structured data
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'excel',
        'application/vnd.ms-excel': 'excel',
        
        # CSV - Python csv module
        'text/csv': 'csv',
        
        # XML/XBRL - Enterprise financial data
        'application/xml': 'xbrl',
        'text/xml': 'xbrl',
        'application/xbrl+xml': 'xbrl',
    }

    def __init__(self):
        self.gemini = GeminiClient()
    
    async def process_file(
        self, 
        file_content: bytes, 
        filename: str, 
        mime_type: str
    ) -> Dict[str, Any]:
        """Process a file and extract structured financial data."""
        file_type = self.SUPPORTED_FORMATS.get(mime_type, 'unknown')
        
        # Auto-detect XBRL by filename extension
        if filename.lower().endswith(('.xbrl', '.xml')) and file_type == 'unknown':
            file_type = 'xbrl'
        
        if file_type == 'csv':
            return await self._process_csv(file_content, filename)
        elif file_type == 'excel':
            return await self._process_excel(file_content, filename)
        elif file_type == 'xbrl':
            return await self._process_xbrl(file_content, filename)
        elif file_type == 'docx':
            return await self._process_docx(file_content, filename)
        elif file_type == 'hwpx':
            return await self._process_hwpx(file_content, filename)
        elif file_type in ('pdf', 'image'):
            return await self._process_with_gemini(file_content, filename, mime_type)
        else:
            raise ValueError(f"Unsupported file type: {mime_type}")

    async def _process_docx(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Process Word document using python-docx and Gemini."""
        # Using global import docx
        doc = docx.Document(io.BytesIO(content))
        full_text = []
        
        # Extract parsing structure
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text)
                
        # Basic table extraction (heuristic)
        tables_data = []
        for table in doc.tables:
            t_rows = []
            for row in table.rows:
                t_rows.append([cell.text.strip() for cell in row.cells])
            if t_rows:
                tables_data.append({
                    "name": f"Table_{len(tables_data)+1}",
                    "headers": t_rows[0],
                    "rows": t_rows[1:]
                })
        
        text_content = "\n".join(full_text)
        
        # Use Gemini to structure and analyze the extracted text
        return await self._analyze_text_with_gemini(text_content, filename, "docx", tables_data)

    async def _process_hwpx(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Process HWPX file by extracting text from XML."""
        text_content = ""
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                # HWPX structure usually has content in Contents/section0.xml
                # But we should search for all section XMLs
                section_files = [f for f in zf.namelist() if f.startswith('Contents/section') and f.endswith('.xml')]
                
                for section_file in sorted(section_files):
                    xml_data = zf.read(section_file)
                    root = ET.fromstring(xml_data)
                    
                    # Extract text from <hp:t> tags (HWPX text tag)
                    # Note: Namespace handling might be needed, but simple search often works
                    # Let's try searching for all text nodes
                    texts = [elem.text for elem in root.iter() if elem.text and elem.text.strip()]
                    text_content += "\n".join(texts) + "\n\n"
                    
        except Exception as e:
            logger.error(f"Error parsing HWPX: {e}")
            raise ValueError(f"Failed to parse HWPX file: {e}")

        if not text_content:
            text_content = "No extractable text found in HWPX file."
            
        return await self._analyze_text_with_gemini(text_content, filename, "hwpx")

    async def _analyze_text_with_gemini(self, text: str, filename: str, file_type: str, pre_extracted_tables: List[Dict] =
