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


import google.generativeai as genai

# Import Exporter
from .exporter import exporter

class GeminiClient:
    """Simple Gemini API client using Official SDK."""
    
    def __init__(self):
        # Load API Key from file if environment variable is not set or dummy
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key == "dummy_key":
            try:
                # Absolute path to Desktop key file
                key_path = r"C:\Users\Administrator\Desktop\제미나이 api.txt"
                if os.path.exists(key_path):
                    with open(key_path, "r", encoding="utf-8") as f:
                        file_key = f.read().strip()
                        if file_key:
                            api_key = file_key
                            logger.info(f"Loaded Gemini API Key from {key_path}")
            except Exception as e:
                logger.warning(f"Failed to load API key from file: {e}")

        self.api_key = api_key
        self.model_name = "gemini-2.0-flash"
        self.model = None
        
        if self.api_key and self.api_key != "dummy_key_for_test":
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
            except Exception as e:
                logger.warning(f"Failed to configure Gemini SDK: {e}")
        
    async def generate_content(self, contents: list, response_mime_type: str = None) -> str:
        """Generate content using Gemini SDK."""
        if not self.model:
            logger.warning("Gemini Model not initialized.")
            return ""
            
        generation_config = {}
        if response_mime_type:
            generation_config["response_mime_type"] = response_mime_type
        
        # Adapt content structure for SDK
        # The internal logic passes lists of dicts with 'parts'.
        # We need to flatten this to what SDK expects.
        
        sdk_contents = []
        for c in contents:
            parts = c.get("parts", [])
            for part in parts:
                if "text" in part:
                    sdk_contents.append(part["text"])
                elif "inline_data" in part:
                    sdk_contents.append({
                        "mime_type": part["inline_data"]["mime_type"],
                        "data": base64.b64decode(part["inline_data"]["data"])
                    })

        try:
            # SDK async generation
            response = await self.model.generate_content_async(sdk_contents, generation_config=generation_config)
            return response.text
        except Exception as e:
            error_str = str(e)
            # [Retry Logic] Robust Exponential Backoff for 429
            if "429" in error_str or "Resource exhausted" in error_str or "429" in repr(e):
                import asyncio
                logger.warning(f"Gemini 429 Limit Hit. Starting Exponential Backoff.")
                
                for attempt in range(1, 4): # Try 3 times: 10s, 20s, 40s
                    wait_time = 10 * (2 ** (attempt - 1))
                    logger.warning(f"Retry Attempt {attempt}/3: Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    
                    try:
                        response = await self.model.generate_content_async(sdk_contents, generation_config=generation_config)
                        logger.info(f"Retry Attempt {attempt} SUCCESS!")
                        return response.text
                    except Exception as retry_err:
                        logger.warning(f"Retry Attempt {attempt} Failed: {retry_err}")
                        if attempt == 3:
                            logger.error("All retry attempts exhausted.")
                            raise retry_err
            
            logger.error(f"Gemini SDK Error: {e}")
            raise e
    
    async def generate_with_file(self, file_content: bytes, mime_type: str, prompt: str, response_mime_type: str = None) -> str:
        """Generate content with inline file data using SDK."""
        # For SDK, we can pass dict directly, no need for base64 string wrapper if we handle it in generate_content
        # But generate_content logic above expects base64 encoded 'inline_data' structure because existing callers use it?
        # Actually existing callers (like _process_with_gemini) call generate_with_file.
        # So we can just call generate_content with the right structure.
        
        # We'll stick to the structure generate_content expects (mimicking the API payload structure for compatibility)
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
        'application/csv': 'csv',
        
        # Plain Text
        'text/plain': 'txt',

        # XML/XBRL - Enterprise financial data
        'application/xml': 'xbrl',
        'text/xml': 'xbrl',
        'application/xbrl+xml': 'xbrl',
        
        # iXBRL (Inline XBRL) - HTML embedded
        'application/xhtml+xml': 'ixbrl',
        'text/html': 'ixbrl', # Generic HTML might be iXBRL
        # Excel / CSV
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'excel',
        'application/vnd.ms-excel': 'excel',
        'text/csv': 'csv',
        'application/csv': 'csv',
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
        
        # Auto-detect XBRL/iXBRL by filename extension
        if file_type == 'unknown' or file_type == 'ixbrl': # Refine generic HTML
            lower_name = filename.lower()
            if lower_name.endswith(('.xbrl', '.xml')):
                file_type = 'xbrl'
            elif lower_name.endswith(('.htm', '.html', '.xhtml')):
                # Check content for iXBRL tags to be sure? 
                # For now assume HTM in this context is iXBRL
                file_type = 'ixbrl'
            elif lower_name.endswith('.csv'):
                file_type = 'csv'
            elif lower_name.endswith(('.xlsx', '.xls')):
                file_type = 'excel'
        
        # v17.0 Spoke C: Hybrid Flow Priority Logic
        # Priority: XBRL (1) > iXBRL (2) > PDF (3) > CSV (4)
        
        result = {}
        if file_type == 'csv':
            result = await self._process_spreadsheet(file_content, filename, 'csv')
        elif file_type == 'excel':
            result = await self._process_spreadsheet(file_content, filename, 'xlsx')
        elif file_type == 'xbrl':
            result = await self._process_xbrl(file_content, filename)
        elif file_type == 'ixbrl':
            result = await self._process_ixbrl(file_content, filename)
            # Fallback logic is inside _process_ixbrl calling _process_unstructured_html if needed
            # But wait, logic was:
            # result = await self._process_ixbrl(file_content, filename)
            # is_empty = not result.get("facts")
            # ...
            # We need to replicate that logic or trust _process_ixbrl to handle fallback?
            # The previous code handled fallback OUTSIDE _process_ixbrl. Let's do it here.
            is_empty = not result.get("facts")
            is_tag_error = result.get("metadata", {}).get("error") and "No iXBRL tags" in result.get("summary", "")
            
            if is_empty or is_tag_error:
                logger.info("iXBRL Parser found 0 facts. Falling back to Unstructured HTML Parser.")
                result = await self._process_unstructured_html(file_content, filename)

        elif file_type == 'docx':
            result = await self._process_docx(file_content, filename)
        elif file_type == 'hwpx':
            result = await self._process_hwpx(file_content, filename)
        elif file_type == 'txt':
            try:
                text_content = file_content.decode('utf-8', errors='ignore')
                result = await self._analyze_text_with_gemini(text_content, filename, "txt")
            except Exception as e:
                 logger.error(f"Error processing TXT file: {e}")
                 raise ValueError(f"Failed to process text content: {e}")
        elif file_type in ('pdf', 'image'):
            result = await self._process_with_gemini(file_content, filename, mime_type)
        else:
            raise ValueError(f"Unsupported file type: {mime_type}")
            
        # Export to Supabase
        if result and "facts" in result:
            exporter.export_facts(result["facts"], result.get("metadata", {}))
            
        return result

    async def _process_unstructured_html(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Process generic HTML using LLM parser."""
        print(f"[DEBUG] _process_unstructured_html called for {filename}")
        from .unstructured_parser import UnstructuredHTMLParser
        from .xbrl_semantic_engine import XBRLSemanticEngine
        
        try:
            parser = UnstructuredHTMLParser(self.gemini)
            # await parser.parse returns (facts, raw_data)
            facts, raw_data = await parser.parse(content, filename)
            print(f"[DEBUG] HTML Parser returned {len(facts)} facts. Raw Title: {raw_data.get('title')}")
        except Exception as e:
            print(f"[ERROR] HTML Parser failed: {e}")
            import traceback
            traceback.print_exc()
            facts, raw_data = [], {}
        
        engine = XBRLSemanticEngine(
            company_name=raw_data.get("title", "Unknown"),
            fiscal_year=raw_data.get("fiscal_year", "2024"),
            file_path=filename
        )
        engine.facts = facts
        qa_pairs = engine._generate_reasoning_qa(facts)
        jsonl = engine._generate_jsonl(qa_pairs)
        
        return {
            "title": raw_data.get("title", filename),
            "summary": "Unstructured HTML analysis complete.",
            "reasoning_qa": qa_pairs,
            "jsonl_data": jsonl,
            "facts": [
                {
                    "concept": f.concept,
                    "label": f.label,
                    "value": str(f.value),
                    "unit": f.unit,
                    "period": f.period,
                    "confidence_score": getattr(f, "confidence_score", 1.0), # v17.0 Export
                    "tags": getattr(f, "tags", [])
                } for f in facts
            ],
            "metadata": {"file_type": "html_unstructured", "company": raw_data.get("title", "Unknown")}
        }

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

    async def _analyze_text_with_gemini(self, text: str, filename: str, file_type: str, pre_extracted_tables: List[Dict] = None) -> Dict[str, Any]:
        """Helper to send text content to Gemini for structuring."""
        prompt = f'''
        You are a Data Collection Expert who does not tolerate omissions.
        
        Analyze the following text extracted from a {file_type} document ({filename}).
        Extract structured financial data into JSON.
        
        Requirements:
        1. [FULL-ROW MAPPING] Remove all 'Key Metric' whitelists. Extract EVERY single row from Balance Sheet, Income Statement, and Cash Flow as individual facts.
        2. [MICROSCOPIC RECOVERY] Deconstruct the Notes section to extract granular data like regional revenue and product segment earnings.
        3. [MINIMUM THRESHOLD] Aim to generate at least 50+ valid facts for this company.
        4. Identify the document title and provide a detailed summary.
        5. If there are tables explicitly mentioned or structured in text, reconstruct them.
        6. Output strictly in JSON.
        7. IMPORTANT: All output must be in English. Translate if necessary.
        
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
        '''
        
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

    async def _process_xbrl(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        Process XBRL/XML file using STRUCTURAL Tree Parser.
        
        [Workflow]
        1. Parse structure with XML Tree Parser
        2. Standardize units via ScaleProcessor ($B)
        3. Filter Contexts (CY/PY mapping)
        4. Infer reasoning Q&A in CoT format
        
        Returns: XBRLIntelligenceResult converted to standard format
        """
        from .xbrl_semantic_engine import XBRLSemanticEngine
        
        # Automatic detection of label linkbase (filename-based)
        label_content = None
        
        # Try to find label file in the same directory as filename (if path exists)
        # Note: 'filename' passed here might be just "foo.xbrl" or full path.
        try:
            # We assume filename passed to ingestion might be a full path or just name.
            # If it is just a name, we can't really find the label file unless we know the upload dir.
            # But in our test script, we pass full path or relative path from CWD.
            
            # 1. Construct potential label filename pattern
            # entity00126380_2024-12-31.xbrl -> entity00126380_2024-12-31_lab-en.xml
            base_path = os.path.splitext(filename)[0]
            
            # Search candidates
            candidates = [
                f"{base_path}_lab-en.xml",
                f"{base_path}_lab-ko.xml", # Fallback to KO if EN missing?
                f"{base_path}_lab.xml"
            ]
            
            for cand in candidates:
                if os.path.exists(cand):
                    logger.info(f"Auto-detected Label Linkbase: {cand}")
                    with open(cand, 'rb') as f:
                        label_content = f.read()
                    break
                    
        except Exception as e:
            logger.warning(f"Label auto-detection failed: {e}")
        
        # Initialize XBRLSemanticEngine and perform structural parsing.
        engine = XBRLSemanticEngine(
            company_name="",  # Extracted during parsing
            fiscal_year="",    # Extracted during parsing
            file_path=filename
        )
        
        try:
            result = engine.process_joint(
                label_content=label_content,
                instance_content=content
            )
            
            if not result.success:
                return {
                    "title": f"XBRL Parsing Failed: {filename}",
                    "summary": result.parse_summary,
                    "tables": [],
                    "key_metrics": {},
                    "facts": [],
                    "parse_log": result.errors,
                    "metadata": {
                        "file_type": "xbrl",
                        "processed_by": "xbrl-semantic-engine-v11.5",
                        "error": True
                    }
                }
            
            # Convert SemanticFacts to standard format
            facts_list = []
            for fact in result.facts:
                facts_list.append({
                    "concept": fact.concept,
                    "label": fact.label,
                    "value": str(fact.value),
                    "raw_value": fact.raw_value,
                    "unit": fact.unit,
                    "period": fact.period,
                    "is_consolidated": fact.is_consolidated,
                    "decimals": fact.decimals,
                    "confidence_score": getattr(fact, "confidence_score", 1.0),
                    "tags": getattr(fact, "tags", [])
                })
            
            # Convert to table format
            tables = self._build_financial_tables(facts_list)

            # CRITICAL DEBUG: Verify Data Pipe before return
            final_qa = copy.deepcopy(result.reasoning_qa)
            
            # [Strict Handover] Defensive Check
            if final_qa is None:
                final_qa = []
            if not isinstance(final_qa, list):
                logger.error(f"CRITICAL HANDOVER ERROR: reasoning_qa is not a list! Type: {type(final_qa)}")
                final_qa = []  # Emergency reset
            
            qa_count = len(final_qa)
            logger.info(f"V11.5 DATA RECOVERED: [{qa_count}] ROWS READY")
            logger.info(f"TRACE 5: Final data count being sent to Exporter: {qa_count}")
            
            return {
                "title": f"XBRL: {result.company_name or filename}",
                "summary": result.parse_summary,
                "tables": tables,
                "key_metrics": result.key_metrics,
                "facts": facts_list,
                "reasoning_qa": final_qa, # CRITICAL: Deep copy pass-through
                "jsonl_data": result.jsonl_data,  # v11.5: Pass pre-verified JSONL
                "financial_report_md": result.financial_report_md,
                "parse_log": [],
                "metadata": {
                    "file_type": "xbrl",
                    "company": result.company_name,
                    "fiscal_year": result.fiscal_year,
                    "fact_count": len(facts_list),
                    "processed_by": "xbrl-semantic-engine-v11.5"
                }
            }
            
        except Exception as e:
            logger.error(f"XBRL Parsing totally failed: {e}")
            return {
                "title": f"XBRL Parsing Error: {filename}",
                "summary": f"Fatal error: {str(e)}",
                "tables": [],
                "key_metrics": {},
                "facts": [],
                "metadata": {
                    "file_type": "xbrl",
                    "error": True,
                    "processed_by": "none"
                }
            }
    
    def _build_financial_tables(self, facts: List[Dict]) -> List[Dict]:
        """Convert facts into financial table format."""
        
        # Balance Sheet items
        balance_sheet = {"name": "Statement of Financial Position (Balance Sheet)", "headers": ["Account", "Amount ($B)", "Period"], "rows": []}
        # Income Statement items
        income_statement = {"name": "Statement of Comprehensive Income (Income Statement)", "headers": ["Account", "Amount ($B)", "Period"], "rows": []}
        # Operational items (Prompt v14.8)
        operational_table = {"name": "Operational & Non-Financial Metrics", "headers": ["Metric", "Value", "Period"], "rows": []}
        
        for fact in facts:
            label = fact.get("label", "")
            value = fact.get("value", "")
            period = fact.get("period", "")
            unit = fact.get("unit", "") # New field
            
            row = [label, value, period]
            
            # [Prompt v14.8] Non-Currency Separation
            is_operational = unit in ['shares', 'number', 'pure', 'ratio'] or \
                             any(k in label.lower() for k in ['share', 'headcount', 'attendance', 'volume', 'units', 'ratio', 'margin', 'rate', 'dividend'])

            if is_operational:
                operational_table["rows"].append(row)
            # [Step 1] Full-Row Mapping
            elif any(k in label.lower() for k in ['revenue', 'profit', 'income', 'loss', 'expens', 'sales', 'ebit', 'cost', 'tax', 'earning']):
                income_statement["rows"].append(row)
            else:
                balance_sheet["rows"].append(row)
        
        tables = []
        if balance_sheet["rows"]: tables.append(balance_sheet)
        if income_statement["rows"]: tables.append(income_statement)
        if operational_table["rows"]: tables.append(operational_table)
            
        return tables

    async def _process_ixbrl(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        Process iXBRL (HTML) file using BeautifulSoup adapter.
        Routes extracted facts to XBRLSemanticEngine.
        """
        from .ixbrl_parser import IXBRLParser
        from .xbrl_semantic_engine import XBRLSemanticEngine
        
        try:
            # 1. Parse iXBRL
            parser = IXBRLParser(content)
            facts = parser.parse()
            meta = parser.get_metadata()
            
            if not facts:
                return {
                    "title": f"iXBRL Parsing Failed: {filename}",
                    "summary": "No iXBRL tags found in HTML.",
                    "tables": [],
                    "key_metrics": {},
                    "facts": [],
                    "metadata": {"file_type": "ixbrl", "error": True}
                }

            # 2. Initialize Engine
            engine = XBRLSemanticEngine(
                company_name=meta.get("company", "Unknown"),
                fiscal_year=meta.get("year", "2024"),
                file_path=filename
            )
            
            # V13.6 FIX: Apply Time Series Logic to iXBRL Facts
            # iXBRL Parser returns raw dates (e.g. "2023-12-31").
            # We must map these to "CY", "PY_..." using the engine's 300-day logic.
            
            # 1. Collect all dates
            raw_dates = [f.period for f in facts]
            date_counts = {}
            for d in raw_dates:
                date_counts[d] = date_counts.get(d, 0) + 1
                
            # 2. Determine CY (Most common date)
            if date_counts:
                cy_date = max(date_counts, key=date_counts.get)
                # Sort descending for PY mapping
                sorted_dates = sorted(date_counts.keys(), reverse=True)
                
                # 3. Create Mapping Dictionary
                period_map = {cy_date: "CY"}
                engine.period_date_map["CY"] = cy_date # V13.7 Inject into Engine
                
                from datetime import datetime
                try:
                    cy_dt = datetime.strptime(cy_date, "%Y-%m-%d")
                    for d_str in sorted_dates:
                        if d_str == cy_date: continue
                        try:
                            d_dt = datetime.strptime(d_str, "%Y-%m-%d")
                            days_diff = (cy_dt - d_dt).days
                            if days_diff >= 300:
                                label = f"PY_{d_str}"
                                period_map[d_str] = label
                                engine.period_date_map[label] = d_str # V13.7 Inject into Engine
                        except: pass
                except: pass
                
                # 4. Apply Mapping to Facts
                valid_facts = []
                for f in facts:
                    if f.period in period_map:
                        f.period = period_map[f.period]
                        # Only keep mapped facts (CY or valid PYs)
                        valid_facts.append(f)
                
                # Replace facts with mapped ones
                facts = valid_facts
            
            # 3. Inject Facts & Generate CoT
            # Note: We need to set engine.facts manually since we skipped _extract_facts
            engine.facts = facts
            
            # Use engine's internal logic to generate CoT
            qa_pairs = engine._generate_reasoning_qa(facts)
            jsonl_data = engine._generate_jsonl(qa_pairs)
            
            # 4. Build Table Representation
            # Convert facts to dict list for table builder
            from .xbrl_semantic_engine import ScaleProcessor
            facts_list = []
            for f in facts:
                # [Step 3] Apply Global Unit Lock logic here for iXBRL facts
                # iXBRL Parser usually extracts raw text. We need to normalize.
                # Use default USD as unit_type for normalization if not specified (safe assumption for Tesla 10-K)
                # However, f.unit should be preserved.
                
                # Check if it looks like a numeric fact
                val_str = str(f.value)
                # Try to normalize if it is numeric and large
                normalized_val = f.value
                
                # Check for ScaleProcessor usage
                try:
                    # Heuristic: If raw value is > 1 million, assume it needs checking
                    # If f.value is already a number/Decimal? IXBRLParser might return float/Decimal.
                    # Let's use ScaleProcessor.apply_self_healing logic but adapted
                    
                    # We re-process the value string through ScaleProcessor to ensure consistency
                    # But ScaleProcessor.apply_self_healing takes (raw_val, decimals, unit_type)
                    
                    unit_type = 'currency'
                    # [Updated Logic] Check both unit AND concept for Shares
                    if 'share' in (f.unit or '').lower() or 'share' in f.concept.lower(): 
                        unit_type = 'shares'
                    elif 'pure' in (f.unit or '').lower(): unit_type = 'ratio'
                    
                    if unit_type == 'currency':
                        # We pass the raw string value to get normalized (Billion) value
                        norm_val, _, _ = ScaleProcessor.apply_self_healing(str(f.value), None, unit_type)
                        
                        # Update the fact value for CoT generation
                        # Note: We are updating the object in the list 'facts' (reference)?
                        # No, 'facts' is a list of objects. We can update f.value.
                        f.value = norm_val
                        
                        # For the display list
                        normalized_val = norm_val
                except Exception as e:
                    pass

                facts_list.append({
                    "concept": f.concept,
                    "label": f.label,
                    "value": str(normalized_val),
                    "period": f.period,
                    "unit": f.unit,
                    "confidence_score": getattr(f, "confidence_score", 1.0),
                    "tags": getattr(f, "tags", [])
                })
            
            # Re-inject normalized facts into engine for CoT generation
            # engine.facts is already set to 'facts' (list of objects), and we modified f.value in place above?
            # Yes, 'f' is a reference to the object in 'facts' list.
            # So engine._generate_reasoning_qa(facts) will use the normalized values.
            
            # Re-run CoT generation with normalized values
            qa_pairs = engine._generate_reasoning_qa(facts)
            jsonl_data = engine._generate_jsonl(qa_pairs)

            tables = self._build_financial_tables(facts_list)
            
            return {
                "title": f"iXBRL: {meta.get('company', filename)}",
                "summary": f"iXBRL extraction successful. Found {len(facts)} facts.",
                "tables": tables,
                "key_metrics": {}, # Could extract from facts
                "facts": facts_list,
                "reasoning_qa": qa_pairs,
                "jsonl_data": jsonl_data,
                "financial_report_md": "# iXBRL Analysis",
                "metadata": {
                    "file_type": "ixbrl",
                    "processed_by": "ixbrl-parser-v1.0 + xbrl-engine-v13.2"
                }
            }
            
        except Exception as e:
            logger.error(f"iXBRL Processing Failed: {e}")
            return {
                "title": f"iXBRL Error: {filename}",
                "summary": str(e),
                "tables": [],
                "key_metrics": {},
                "metadata": {"file_type": "ixbrl", "error": True}
            }

    async def _process_spreadsheet(self, content: bytes, filename: str, file_type: str) -> Dict[str, Any]:
        """Process Excel/CSV using SpreadsheetParser."""
        print(f"[DEBUG] _process_spreadsheet called for {filename} ({file_type})")
        from .spreadsheet_parser import SpreadsheetParser
        from .xbrl_semantic_engine import XBRLSemanticEngine
        
        try:
            parser = SpreadsheetParser(content, file_type)
            facts = parser.parse()
            print(f"[DEBUG] Parser returned {len(facts)} facts")
        except Exception as e:
            print(f"[ERROR] SpreadsheetParser failed: {e}")
            import traceback
            traceback.print_exc()
            facts = []
        
        # Default fiscal year fallback if not found
        fiscal_year = "2024" 
        
        engine = XBRLSemanticEngine(
            company_name=filename.replace('.xlsx', '').replace('.csv', ''),
            fiscal_year=fiscal_year,
            file_path=filename
        )
        engine.facts = facts
        
        # Generate QA
        qa_pairs = engine._generate_reasoning_qa(facts)
        jsonl = engine._generate_jsonl(qa_pairs)
        
        return {
            "title": f"Spreadsheet Data: {filename}",
            "summary": f"Extracted {len(facts)} data points from {file_type.upper()}.",
            "reasoning_qa": qa_pairs,
            "jsonl_data": jsonl,
            "facts": [
                {
                    "label": f.label, 
                    "value": str(f.value), 
                    "period": f.period, 
                    "unit": f.unit,
                    "confidence_score": getattr(f, "confidence_score", 1.0),
                    "tags": getattr(f, "tags", [])
                }
                for f in facts
            ],
            "tables": self._build_financial_tables([
                {"label": f.label, "value": str(f.value), "period": f.period, "unit": f.unit}
                for f in facts
            ]),
            "metadata": {"file_type": file_type}
        }

    
    async def _process_with_gemini(self, content: bytes, filename: str, mime_type: str) -> Dict[str, Any]:
        """
        Process PDF/Image using Gemini multimodal via HTTP.
        ENHANCED: Routes processed data through XBRLSemanticEngine for standardized CoT generation.
        """
        from .xbrl_semantic_engine import XBRLSemanticEngine
        from .pdf_adapter import PDFSemanticAdapter
        
        prompt = '''
        You are a Data Collection Expert who does not tolerate omissions.
        
        Analyze this financial document thoroughly. Extract ALL data into structured JSON.
        
        Requirements:
        1. [FULL-ROW MAPPING] Remove all 'Key Metric' whitelists. Extract EVERY single row from Balance Sheet, Income Statement, and Cash Flow as individual facts.
        2. [MICROSCOPIC RECOVERY] Deconstruct the Notes section to extract granular data like regional revenue and product segment earnings.
        3. [MINIMUM THRESHOLD] Aim to generate at least 50+ valid facts for this company.
        4. Identify the document title and provide a detailed summary
        5. Extract ALL tables with proper headers (especially years like 2023, 2024) and data
        6. Identify key financial metrics (revenue, profit, growth rates, ratios)
        7. Note any currency units (KRW, USD, etc.)
        8. Identify date references and time periods
        9. IMPORTANT: All output must be in English. Translate if necessary.
        
        Output JSON format:
        {
            "title": "Document Title",
            "summary": "Detailed summary of the document content",
            "tables": [
                {
                    "name": "Table Name",
                    "headers": ["Column1", "2024", "2023"],
                    "rows": [["Revenue", "150.5", "140.2"], ...]
                }
            ],
            "key_metrics": {
                "Revenue": "150.5B",
                "NetIncome": "20.5B"
            },
            "currency": "USD",
            "date_range": "2024"
        }
        '''
        
        # 1. Get Unstructured Data from Gemini
        try:
            response_text = await self.gemini.generate_with_file(
                content, mime_type, prompt, "application/json"
            )
            gemini_result = json.loads(response_text)
            
            # [Resilience] Handle case where LLM returns a list of facts/tables directly instead of dict
            if isinstance(gemini_result, list):
                # Heuristic: Check if list items look like tables
                is_table_list = False
                if gemini_result and isinstance(gemini_result[0], dict) and ("headers" in gemini_result[0] or "rows" in gemini_result[0]):
                    is_table_list = True
                
                if is_table_list:
                    logger.warning("Gemini returned a LIST of TABLES. Mapping to 'tables' key.")
                    gemini_result = {
                        "title": filename, 
                        "fiscal_year": "2024", 
                        "tables": gemini_result,
                        "key_metrics": {}
                    }
                else:
                    logger.warning("Gemini returned a LIST instead of JSON object in Ingestion Service. Wrapping in default structure.")
                    gemini_result = {
                        "title": filename, 
                        "fiscal_year": "2024", 
                        "tables": [], 
                        "key_metrics": {}, 
                        "raw_list_data": gemini_result
                    }

        except Exception as e:
            logger.warning(f"Gemini Vision API failed: {e}. Falling back to Local PDF Parser.")
            # Fallback to UnstructuredHTMLParser (which supports PDF via pypdf)
            return await self._process_unstructured_html(content, filename)

        # 2. Initialize Engine (for CoT generation)
        # Extract metadata from Gemini result if possible
        doc_title = gemini_result.get("title", filename)
        fiscal_year = "2024" # Default fallback, adapter tries to be smart
        if "2023" in doc_title: fiscal_year = "2023"
        if "2025" in doc_title: fiscal_year = "2025"
        
        engine = XBRLSemanticEngine(
            company_name=doc_title,
            fiscal_year=fiscal_year,
            file_path=filename
        )
        
        # 3. Adapt Data to SemanticFacts
        adapter = PDFSemanticAdapter(doc_title, fiscal_year)
        facts = adapter.adapt(gemini_result)
        
        # 4. Generate Reasoning QA (CoT)
        # We manually inject facts since we skipped XML parsing
        engine.facts = facts
        engine.company_name = doc_title # Ensure consistency
        
        # [Prompt #2: Multi-Source Cross Validation Stub]
        # "Instructions: Cross-verify iXBRL assets with PDF assets..."
        # Since we are in _process_with_gemini (PDF), we don't have iXBRL context here.
        # But we can flag potential inconsistencies if we had reference data.
        # For now, we strictly follow Prompt #4 (Metadata Guard) by enforcing the extracted title/year.
        
        qa_pairs = engine._generate_reasoning_qa(facts)
        jsonl_data = engine._generate_jsonl(qa_pairs)
        
        # 5. Merge Results
        gemini_result["facts"] = [
            {
                "concept": f.concept,
                "value": str(f.value),
                "unit": f.unit,
                "period": f.period,
                "confidence_score": getattr(f, "confidence_score", 1.0),
                "tags": getattr(f, "tags", [])
            } for f in facts
        ]
        gemini_result["reasoning_qa"] = qa_pairs
        gemini_result["jsonl_data"] = jsonl_data
        
        gemini_result["metadata"] = {
            "file_type": "pdf" if "pdf" in mime_type else "image",
            "processed_by": "gemini-2.0-flash + xbrl-engine-v13.2"
        }
        
        return gemini_result
    
    async def _generate_summary(self, data_sample: str) -> str:
        """Generate a summary using Gemini."""
        if not data_sample:
            return "No text content available for summary."
            
        try:
            # V13.8 Resilience: If dummy key or API fails, return fallback summary
            if self.gemini.api_key == "dummy_key_for_test":
                logger.warning("Using dummy key, skipping LLM summary generation.")
                return "Summary unavailable (Test Mode)."

            prompt = f"Summarize the key findings of the following data in 2-3 sentences:\n\n{data_sample}"
            
            contents = [{"parts": [{"text": prompt}]}]
            return await self.gemini.generate_content(contents)
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            return "Summary unavailable due to API error."
    
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
