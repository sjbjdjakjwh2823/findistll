import logging
import json
import re
import os
import google.generativeai as genai
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .xbrl_semantic_engine import SemanticFact
from .pdf_adapter import PDFSemanticAdapter
import pypdf
import io
from collections import Counter

logger = logging.getLogger(__name__)

class UnstructuredHTMLParser:
    """
    Parses generic HTML/PDF with Enhanced Full-Row Mapping & Global Unit Locking.
    v16.0: Asura Identity & Intelligent Imputation Prompting.
    v17.0: Refined False Positive Blocking for Unit Lock.
    """
    
    def __init__(self, gemini_client):
        self.gemini = gemini_client
        self.model = None
        
        # Configure Official Gemini SDK
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key and hasattr(gemini_client, 'api_key'):
             api_key = gemini_client.api_key
             
        if api_key and api_key != "dummy_key_for_test":
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-2.0-flash')
            except Exception as e:
                logger.warning(f"Failed to configure Gemini SDK: {e}")

    async def parse(self, content: bytes, filename: str) -> tuple[List[SemanticFact], Dict[str, Any]]:
        """Main parsing logic with fallback."""
        
        is_pdf = filename.lower().endswith('.pdf')
        text_content = ""

        try:
            # 1. Try Gemini (Best Quality)
            if self.model:
                prompt = '''
                You are 'FinDistill: asura v16.0', the Ultimate AI Economist and Digital Forensic Accountant.
                Your goal is not just extraction, but reconstructing the economic reality of the entity.
                
                Task: Extract financial facts from unstructured HTML/Text content.

                Requirements (v16.0 Core Logic):
                1. [FULL-ROW MAPPING] Remove all 'Key Metric' whitelists. Extract EVERY single row from Balance Sheet, Income Statement, and Cash Flow as individual facts.
                2. [1,000X SCALING CORRECTION (Boeing Fix)] If a currency value is > 1,000 (e.g., 77,794), it is likely "Millions interpreted as Billions". Divide by 1,000 immediately (77,794 -> 77.794). EXCEPTION: Market Cap or Total Assets of Big Tech (>1T).
                3. [BLOCK NON-CURRENCY MONETIZATION] Do NOT add '$' or 'B' to 'Attendance', 'Headcount', 'Shares', 'Volume', 'Units'. Keep them as raw numbers or with specific units.
                4. [FORCED PAIRING & IMPUTATION] For every extracted fact, strictly identify CY and PY. If PY is missing but context suggests it exists, mark as [Missing].
                5. [OUTLIER CHECK] If value > 10,000 or < 0.0001, double-check context.
                
                Output JSON:
                {
                    "title": "Document Title",
                    "fiscal_year": "2024",
                    "tables": [
                        {
                            "name": "Extracted Table",
                            "headers": ["Metric", "2024", "2023"],
                            "rows": [["Revenue", "100", "90"], ["Headcount", "5000", "4800"]]
                        }
                    ]
                }
                '''
                
                # Use Official SDK
                mime_type = "application/pdf" if is_pdf else "text/html"
                response = self.model.generate_content([
                    prompt,
                    {"mime_type": mime_type, "data": content}
                ])
                
                response_text = response.text
                
                try:
                    gemini_result = json.loads(response_text)
                    
                    # [Debug]
                    logger.info(f"Gemini response type: {type(gemini_result)}")

                    # [Resilience] Handle case where LLM returns a list of facts/tables directly instead of dict
                    if not isinstance(gemini_result, dict):
                        logger.warning(f"Gemini returned {type(gemini_result)} instead of dict. Wrapping in default structure.")
                        gemini_result = {
                            "title": filename, 
                            "fiscal_year": "2024", 
                            "tables": [], 
                            "key_metrics": {}, 
                            "raw_list_data": gemini_result
                        }

                    adapter = PDFSemanticAdapter(gemini_result.get("title", filename), gemini_result.get("fiscal_year", "2024"))
                    facts = adapter.adapt(gemini_result)
                    
                    if len(facts) > 20: 
                        logger.info(f"Gemini Extraction Success: {len(facts)} facts found.")
                        return facts, gemini_result
                        
                except json.JSONDecodeError:
                    logger.warning("Gemini returned invalid JSON. Falling back.")
        except Exception as e:
            logger.warning(f"Gemini parsing failed, switching to local fallback: {e}")

        # 2. Local Fallback (Text Extraction)
        if is_pdf:
            try:
                reader = pypdf.PdfReader(io.BytesIO(content))
                for i, page in enumerate(reader.pages[:20]): 
                    text = page.extract_text()
                    if text: text_content += text + "\n"
                if not text_content: raise ValueError("Empty text from PDF")
            except Exception as e:
                logger.warning(f"PDF extraction failed: {e}. Checking HTML...")
                try:
                    soup = BeautifulSoup(content, 'html.parser')
                    text_content = soup.get_text(separator='\n')
                except: return [], {}
        else:
            soup = BeautifulSoup(content, 'html.parser')
            for tag in soup.find_all(['tr', 'p', 'div', 'h1', 'h2', 'h3', 'br', 'li']): tag.insert_after('\n')
            for tag in soup.find_all(['td', 'th']): tag.insert_after(' ')
            text_content = soup.get_text()

        # 3. Heuristic Extraction
        millions_count = len(re.findall(r'(?:in\s+)?millions?', text_content, re.IGNORECASE))
        billions_count = len(re.findall(r'(?:in\s+)?billions?', text_content, re.IGNORECASE))
        
        global_scale = 1.0
        if billions_count > millions_count: global_scale = 1_000_000_000.0
        elif millions_count > 0: global_scale = 1_000_000.0

        years = re.findall(r'20\d{2}', text_content)
        year_counts = Counter(years)
        cy_year = "2024"
        py_year = "2023"
        if year_counts:
            top_years = [y for y, c in year_counts.most_common(2)]
            top_years.sort(reverse=True)
            if len(top_years) >= 1: cy_year = top_years[0]
            if len(top_years) >= 2: py_year = top_years[1]
            else: py_year = str(int(cy_year) - 1)

        extracted_data = {"tables": [{"name": "Full-Row Extraction", "headers": ["Metric", cy_year, py_year], "rows": []}], "key_metrics": {}}
        
        # Blocklist for False Positives (v17.0 refinement)
        NON_FINANCIAL_KEYWORDS = [
            "employee", "headcount", "people", "worker", "student", "attendee", "visitor",
            "vehicle", "car", "unit", "patent", "store", "location", "branch",
            "page", "note", "item", "table", "california", "texas", "area" 
        ]

        for line in text_content.split('\n'):
            line = line.strip()
            if not line or len(line) > 200: continue
            numbers = list(re.finditer(r'(-?\(?[\d,]+\.?\d*\)?)', line))
            if not numbers: continue

            first_num_idx = numbers[0].start()
            label_text = re.sub(r'[^\w\s\(\)&/-]', '', line[:first_num_idx].strip()).strip()
            if not label_text or len(label_text) < 3 or label_text.lower() in ["item", "page", "table", "note"]: continue
            
            # Skip non-financial lines entirely if heuristic
            if any(k in label_text.lower() for k in NON_FINANCIAL_KEYWORDS):
                continue

            valid_nums = []
            for match in numbers:
                clean_str = match.group(0).replace(',', '').replace('$', '').strip()
                is_negative = False
                if '(' in clean_str and ')' in clean_str: is_negative = True; clean_str = clean_str.replace('(', '').replace(')', '')
                elif clean_str.startswith('-'): is_negative = True; clean_str = clean_str.lstrip('-')
                
                try:
                    if not clean_str: continue
                    val_float = float(clean_str)
                    if 1990 <= val_float <= 2030 and val_float.is_integer() and '.' not in match.group(0): continue
                    if is_negative: val_float = -val_float

                    # [Step 3] Global Unit Lock for Unstructured Data
                    # Normalize to Billions ($B)
                    val_scaled = val_float
                    
                    if 'eps' not in label_text.lower() and 'per share' not in label_text.lower():
                        if global_scale >= 1_000_000_000.0: # Billions
                            val_scaled = val_float
                        elif global_scale >= 1_000_000.0: # Millions
                             val_scaled = val_float / 1000.0
                        else: # Ones
                             val_scaled = val_float / 1_000_000_000.0
                        
                        # Boeing Rule / Outlier Check
                        threshold = 10000.0
                        if 'share' in label_text.lower() or 'volume' in label_text.lower():
                            threshold = 100000.0

                        if abs(val_scaled) > threshold:
                             while abs(val_scaled) > threshold:
                                 val_scaled /= 1000.0

                    valid_nums.append(str(val_scaled))
                except: continue

            if len(valid_nums) >= 2: extracted_data["tables"][0]["rows"].append([label_text, valid_nums[-2], valid_nums[-1]])
            elif len(valid_nums) == 1: extracted_data["tables"][0]["rows"].append([label_text, valid_nums[0], ""])
        
        adapter = PDFSemanticAdapter(filename, cy_year)
        facts = adapter.adapt(extracted_data)
        return facts, {"title": filename, "fiscal_year": cy_year, "source": "Enhanced Full-Row Parser"}
