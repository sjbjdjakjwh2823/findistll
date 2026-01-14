"""
FinDistill File Ingestion Service

Handles parsing of various file formats:
- PDF (with complex table extraction)
- Excel (.xlsx, .xls)
- CSV (with auto-detection)
- Images (via Gemini multimodal)
"""

import io
import json
from typing import Dict, Any, List, Optional
import google.generativeai as genai


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
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    async def process_file(
        self, 
        file_content: bytes, 
        filename: str, 
        mime_type: str
    ) -> Dict[str, Any]:
        """
        Process a file and extract structured financial data.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            mime_type: MIME type of the file
            
        Returns:
            Extracted data with metadata
        """
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
        """Process CSV file using pandas."""
        import pandas as pd
        
        # Try different encodings
        for encoding in ['utf-8', 'cp949', 'euc-kr', 'latin1']:
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Could not decode CSV file with any supported encoding")
        
        # Convert to structured format
        tables = [{
            "name": filename,
            "headers": df.columns.tolist(),
            "rows": df.values.tolist()
        }]
        
        # Generate summary using Gemini
        sample_data = df.head(10).to_string()
        summary = await self._generate_summary(sample_data)
        
        return {
            "title": filename,
            "summary": summary,
            "tables": tables,
            "key_metrics": self._extract_metrics(df),
            "metadata": {
                "file_type": "csv",
                "row_count": len(df),
                "column_count": len(df.columns)
            }
        }
    
    async def _process_excel(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Process Excel file using openpyxl/pandas."""
        import pandas as pd
        
        # Read all sheets
        excel_file = pd.ExcelFile(io.BytesIO(content))
        tables = []
        all_metrics = {}
        
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            
            # Skip empty sheets
            if df.empty:
                continue
                
            tables.append({
                "name": sheet_name,
                "headers": df.columns.tolist(),
                "rows": df.fillna("").values.tolist()
            })
            
            # Merge metrics from each sheet
            sheet_metrics = self._extract_metrics(df)
            all_metrics.update({f"{sheet_name}_{k}": v for k, v in sheet_metrics.items()})
        
        # Generate summary
        sample_text = "\n".join([t["name"] + ": " + str(t["headers"]) for t in tables[:3]])
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
    
    async def _process_with_gemini(
        self, 
        content: bytes, 
        filename: str, 
        mime_type: str
    ) -> Dict[str, Any]:
        """Process PDF/Image using Gemini multimodal."""
        
        # Upload to Gemini
        gemini_file = genai.upload_file(
            io.BytesIO(content),
            mime_type=mime_type,
            display_name=filename
        )
        
        # Enhanced prompt for financial documents
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
            "date_range": "YYYY-MM-DD to YYYY-MM-DD",
            "document_type": "재무제표/손익계산서/etc"
        }
        
        Be thorough and extract all numerical data visible in the document.
        """
        
        response = self.model.generate_content(
            [gemini_file, prompt],
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Clean up uploaded file
        try:
            genai.delete_file(gemini_file.name)
        except Exception:
            pass
        
        result = json.loads(response.text)
        result["metadata"] = {
            "file_type": "pdf" if "pdf" in mime_type else "image",
            "processed_by": "gemini-1.5-flash"
        }
        
        return result
    
    async def _generate_summary(self, data_sample: str) -> str:
        """Generate a summary using Gemini."""
        prompt = f"""
        다음 데이터의 핵심 내용을 2-3문장으로 요약해주세요:
        
        {data_sample}
        """
        
        response = self.model.generate_content(prompt)
        return response.text.strip()
    
    def _extract_metrics(self, df) -> Dict[str, Any]:
        """Extract key metrics from a pandas DataFrame."""
        import pandas as pd
        
        metrics = {}
        
        # Find numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns
        
        for col in numeric_cols[:5]:  # Limit to first 5 numeric columns
            if len(df[col].dropna()) > 0:
                metrics[f"{col}_total"] = float(df[col].sum())
                metrics[f"{col}_avg"] = float(df[col].mean())
        
        return metrics


# Singleton instance
ingestion_service = FileIngestionService()
