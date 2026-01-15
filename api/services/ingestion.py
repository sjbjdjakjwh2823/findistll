"""
FinDistill File Ingestion Service

Handles parsing of various file formats using Gemini API via HTTP.
- PDF (with complex table extraction)
- Excel (.xlsx, .xls)
- CSV (with auto-detection)
- Images (via Gemini multimodal)
"""

import io
import json
import csv
import base64
from typing import Dict, Any, List, Optional
import httpx
import os

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
    
    SUPPORTED_FORMATS = {
        'application/pdf': 'pdf',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'excel',
        'application/vnd.ms-excel': 'excel',
        'text/csv': 'csv',
        'image/png': 'image',
        'image/jpeg': 'image',
        'image/webp': 'image',
        'image/heic': 'image',
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
        
        if file_type == 'csv':
            return await self._process_csv(file_content, filename)
        elif file_type == 'excel':
            return await self._process_excel(file_content, filename)
        elif file_type in ('pdf', 'image'):
            return await self._process_with_gemini(file_content, filename, mime_type)
        else:
            raise ValueError(f"Unsupported file type: {mime_type}")
    
    async def _process_csv(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Process CSV file using standard csv module."""
        text_content = None
        
        # Try different encodings
        for encoding in ['utf-8', 'cp949', 'euc-kr', 'latin1']:
            try:
                text_content = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if text_content is None:
            raise ValueError("Could not decode CSV file with any supported encoding")
        
        # Parse CSV
        f = io.StringIO(text_content)
        reader = csv.reader(f)
        rows = list(reader)
        
        if not rows:
            return {"title": filename, "summary": "Empty CSV file", "tables": []}
            
        headers = rows[0]
        data_rows = rows[1:]
        
        tables = [{
            "name": filename,
            "headers": headers,
            "rows": data_rows
        }]
        
        # Generate summary using Gemini
        sample_lines = rows[:10]
        sample_data = "\n".join([",".join(map(str, row)) for row in sample_lines])
        summary = await self._generate_summary(sample_data)
        
        return {
            "title": filename,
            "summary": summary,
            "tables": tables,
            "key_metrics": self._extract_metrics(headers, data_rows),
            "metadata": {
                "file_type": "csv",
                "row_count": len(rows),
                "column_count": len(headers)
            }
        }
    
    async def _process_excel(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Process Excel file using openpyxl."""
        from openpyxl import load_workbook
        
        wb = load_workbook(filename=io.BytesIO(content), data_only=True)
        tables = []
        all_metrics = {}
        
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.values)
            
            if not rows:
                continue
                
            headers = list(rows[0]) if rows else []
            data_rows = [list(row) for row in rows[1:]] if len(rows) > 1 else []
            
            # Simple conversion of None to empty string
            headers = [str(h) if h is not None else "" for h in headers]
            data_rows = [[cell if cell is not None else "" for cell in row] for row in data_rows]
            
            tables.append({
                "name": sheet_name,
                "headers": headers,
                "rows": data_rows
            })
            
            # Merge metrics
            sheet_metrics = self._extract_metrics(headers, data_rows)
            all_metrics.update({f"{sheet_name}_{k}": v for k, v in sheet_metrics.items()})
        
        # Generate summary
        sample_text = "\n".join([f"{t['name']}: {t['headers']}" for t in tables[:3]])
        summary = await self._generate_summary(sample_text)
        
        return {
            "title": filename,
            "summary": summary,
            "tables": tables,
            "key_metrics": all_metrics,
            "metadata": {
                "file_type": "excel",
                "sheet_count": len(tables)
            }
        }
    
    async def _process_with_gemini(self, content: bytes, filename: str, mime_type: str) -> Dict[str, Any]:
        """Process PDF/Image using Gemini multimodal via HTTP."""
        prompt = """
        Analyze this financial document thoroughly. Extract ALL data into structured JSON.
        
        Requirements:
        1. Identify the document title and provide a detailed summary
        2. Extract ALL tables with proper headers and data
        3. Identify key financial metrics (revenue, profit, growth rates, ratios)
        4. Note any currency units (KRW, USD, etc.)
        5. Identify date references and time periods
        
        Output JSON format:
        {
            "title": "Document Title",
            "summary": "Detailed summary of the document content",
            "tables": [
                {
                    "name": "Table Name",
                    "headers": ["Column1", "Column2", ...],
                    "rows": [["Value1", "Value2", ...], ...]
                }
            ],
            "key_metrics": {
                "metric_name": "value with unit"
            },
            "currency": "KRW or USD",
            "date_range": "YYYY-MM-DD to YYYY-MM-DD"
        }
        """
        
        response_text = await self.gemini.generate_with_file(
            content, mime_type, prompt, "application/json"
        )
        
        result = json.loads(response_text)
        result["metadata"] = {
            "file_type": "pdf" if "pdf" in mime_type else "image",
            "processed_by": "gemini-2.0-flash"
        }
        
        return result
    
    async def _generate_summary(self, data_sample: str) -> str:
        """Generate a summary using Gemini."""
        prompt = f"다음 데이터의 핵심 내용을 2-3문장으로 요약해주세요:\n\n{data_sample}"
        
        contents = [{"parts": [{"text": prompt}]}]
        return await self.gemini.generate_content(contents)
    
    def _extract_metrics(self, headers: List[str], rows: List[List[Any]]) -> Dict[str, Any]:
        """Extract simple metrics from headers and rows without pandas."""
        metrics = {}
        if not headers or not rows:
            return metrics

        # Find potential numeric columns (simple heuristic)
        numeric_indices = []
        for i in range(len(headers)):
            # Check first few non-empty rows
            is_numeric = False
            for row in rows[:5]:
                if i < len(row) and isinstance(row[i], (int, float)):
                   is_numeric = True
                   break
                elif i < len(row) and isinstance(row[i], str) and row[i].replace('.','',1).isdigit():
                   is_numeric = True
                   break
            if is_numeric:
                numeric_indices.append(i)
        
        # Calculate sums/averages for first few numeric columns
        for i in numeric_indices[:5]:
            col_name = str(headers[i])
            values = []
            for row in rows:
                if i < len(row):
                    val = row[i]
                    try:
                        if isinstance(val, (int, float)):
                            values.append(float(val))
                        elif isinstance(val, str):
                            # clean string
                            clean_val = val.replace(',', '').replace(' ', '')
                            if clean_val:
                                values.append(float(clean_val))
                    except ValueError:
                        continue
            
            if values:
                metrics[f"{col_name}_total"] = sum(values)
                metrics[f"{col_name}_avg"] = sum(values) / len(values)
                
        return metrics

ingestion_service = FileIngestionService()
