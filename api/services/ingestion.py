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
        import docx
        
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
            print(f"Error parsing HWPX: {e}")
            raise ValueError(f"Failed to parse HWPX file: {e}")

        if not text_content:
            text_content = "No extractable text found in HWPX file."
            
        return await self._analyze_text_with_gemini(text_content, filename, "hwpx")

    async def _analyze_text_with_gemini(self, text: str, filename: str, file_type: str, pre_extracted_tables: List[Dict] = None) -> Dict[str, Any]:
        """Helper to send text content to Gemini for structuring."""
        prompt = f"""
        Analyze the following text extracted from a {file_type} document ({filename}).
        Extract structured financial data into JSON.
        
        Text Content:
        {text[:30000]}  # Limit context window if necessary, though Gemini Flash has 1M window
        
        Requirements:
        1. Identify the document title and provide a detailed summary.
        2. Identify key financial metrics (revenue, profit, ratios).
        3. If there are tables explicitly mentioned or structured in text, reconstruct them.
        4. Output strictly in JSON.
        
        Output JSON format:
        {{
            "title": "Document Title",
            "summary": "Detailed summary",
            "tables": [
                {{
                    "name": "Table Name",
                    "headers": ["Col1", "Col2"],
                    "rows": [["Val1", "Val2"]]
                }}
            ],
            "key_metrics": {{ "metric": "value" }},
            "currency": "KRW/USD",
            "date_range": "YYYY-MM-DD"
        }}
        """
        
        response_text = await self.gemini.generate_content(
            [{"parts": [{"text": prompt}]}], 
            "application/json"
        )
        
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Fallback if valid JSON isn't returned
            result = {
                "title": filename, 
                "summary": "AI processing error", 
                "tables": [], 
                "key_metrics": {}
            }
            
        # Merge pre-extracted tables if AI didn't find them but we did (e.g. from DOCX)
        if pre_extracted_tables and not result.get("tables"):
            result["tables"] = pre_extracted_tables
            
        result["metadata"] = {
            "file_type": file_type,
            "processed_by": "gemini-2.0-flash-text"
        }
        
        return result
    
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
