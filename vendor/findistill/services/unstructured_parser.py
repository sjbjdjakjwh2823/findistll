import logging
import json
import re
import os
from html import unescape
from typing import List, Dict, Any, Optional
from .xbrl_semantic_engine import SemanticFact
from .pdf_adapter import PDFSemanticAdapter
import io
from decimal import Decimal, InvalidOperation
from collections import Counter

logger = logging.getLogger(__name__)


def _text_sufficient(text: str, min_chars: Optional[int] = None) -> bool:
    if min_chars is None:
        try:
            min_chars = int(os.getenv("PDF_TEXT_MIN_CHARS", "200") or "200")
        except (TypeError, ValueError):
            min_chars = 200
    return bool(text and len(text.strip()) >= min_chars)


def _select_pdf_text_content(text_layer: str, ocr_text: str) -> str:
    """
    Prefer text-layer when sufficient; otherwise fall back to OCR if it has content.
    """
    if _text_sufficient(text_layer):
        return text_layer
    if ocr_text and len(ocr_text.strip()) > 0:
        return ocr_text
    return text_layer or ocr_text or ""

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
             
        # Never auto-enable Gemini here. It must be explicitly enabled.
        if os.getenv("GEMINI_ENABLED", "0") == "1" and api_key and api_key != "dummy_key_for_test":
            try:
                # Prefer new SDK if available.
                try:
                    import google.genai as genai
                    from google.genai import types
                    self._genai_client = genai.Client(api_key=api_key)
                    self._genai_types = types
                    self._model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
                    self.model = "genai"
                except (ImportError, AttributeError, RuntimeError, ValueError) as new_err:
                    logger.warning(f"google.genai unavailable, falling back to google.generativeai: {new_err}")
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    self.model = genai.GenerativeModel('gemini-2.0-flash')
            except (ImportError, AttributeError, RuntimeError, ValueError) as e:
                logger.warning(f"Failed to configure Gemini SDK: {e}")

    async def parse(self, content: bytes, filename: str) -> tuple[List[SemanticFact], Dict[str, Any]]:
        """Main parsing logic with fallback."""
        
        lower_name = filename.lower()
        # Don't rely on the filename alone (some uploads are HTML/JSON with a .pdf extension).
        is_pdf = lower_name.endswith('.pdf') and content.lstrip().startswith(b"%PDF")
        is_image = lower_name.endswith(('.png', '.jpg', '.jpeg', '.tiff', '.webp', '.heic'))
        text_content = ""

        try:
            # 1. Try Gemini only if explicitly enabled (default off).
            if self.model and os.getenv("GEMINI_ENABLED", "0") == "1":
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
                
                mime_type = "application/pdf" if is_pdf else "text/html"
                if self.model == "genai":
                    # New SDK (sync) with Parts
                    parts = [
                        self._genai_types.Part.from_text(text=prompt),
                        self._genai_types.Part.from_bytes(data=content, mime_type=mime_type),
                    ]
                    response = self._genai_client.models.generate_content(
                        model=self._model_name,
                        contents=parts,
                        config={"response_mime_type": "application/json"},
                    )
                    response_text = response.text
                else:
                    # Legacy SDK
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
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Gemini parsing failed, switching to local fallback: {e}")

        # 2. Local Fallback (Text Extraction)
        if is_pdf:
            # Operator requirement: OCR-first (Vision preferred), then fall back to local parsing.
            # Default is OCR-first to maximize extraction quality.
            text_layer_probe_first = os.getenv("PDF_TEXT_LAYER_PROBE_FIRST", "0") == "1"
            ocr_probe_text = ""
            ocr_first = os.getenv("PDF_OCR_FIRST", "1") == "1"
            ocr_force = os.getenv("PDF_OCR_FORCE", "1") == "1"

            # Optional reliability/performance mode:
            # If the PDF has a sufficient text layer, skip OCR entirely.
            # This preserves current default behavior unless explicitly enabled.
            text_layer = ""
            if text_layer_probe_first:
                try:
                    import pypdf

                    reader = pypdf.PdfReader(io.BytesIO(content))
                    for page in reader.pages[:20]:
                        t = page.extract_text()
                        if t:
                            text_layer += t + "\n"
                except (ImportError, OSError, ValueError) as e:
                    logger.warning(f"PDF extraction failed: {e}.")
                    text_layer = ""
                if _text_sufficient(text_layer):
                    text_content = text_layer
                    # Final selection: keep deterministic text-layer if it is sufficient.
                    text_content = _select_pdf_text_content(text_content, "")
                else:
                    text_layer = ""

            if text_layer_probe_first and _text_sufficient(text_content):
                # We already selected text-layer; do not OCR probe.
                ocr_first = False
                ocr_force = False

            if ocr_first:
                try:
                    ocr_probe_pages = int(os.getenv("PDF_OCR_FIRST_PAGES", "1") or "1")
                    ocr_probe_text = await _extract_text_from_pdf_images_async(content, max_pages=ocr_probe_pages)
                except (ImportError, OSError, RuntimeError, ValueError):
                    ocr_probe_text = ""

            # Local text-layer parse (pypdf) is the fallback when OCR is empty/insufficient.
            if not text_layer:
                try:
                    import pypdf

                    reader = pypdf.PdfReader(io.BytesIO(content))
                    for page in reader.pages[:20]:
                        t = page.extract_text()
                        if t:
                            text_layer += t + "\n"
                except (ImportError, OSError, ValueError) as e:
                    logger.warning(f"PDF extraction failed: {e}.")
                    text_layer = ""

            # If OCR indicates usable content and OCR is forced, do full OCR.
            # Otherwise, fall back to text layer if it is sufficient.
            if ocr_force and _text_sufficient(ocr_probe_text):
                text_content = await _extract_text_from_pdf_images_async(content)
            elif _text_sufficient(ocr_probe_text) and not _text_sufficient(text_layer):
                text_content = await _extract_text_from_pdf_images_async(content)
            else:
                text_content = text_layer

            # Final selection: prefer sufficient text-layer unless OCR is the only usable signal.
            text_content = _select_pdf_text_content(text_content, ocr_probe_text)
        elif is_image:
            text_content = await _extract_text_from_image_async(content)
        else:
            text_content = await _extract_text_from_html_async(content)

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

        # PDF-first: try structural table extraction before noisy line heuristics.
        # This yields much higher-quality financial statement rows for 10-Q/10-K style PDFs.
        if is_pdf:
            try:
                pdf_tables = _extract_tables_from_pdf(content, cy_year=cy_year, py_year=py_year, global_scale=global_scale)
                if pdf_tables:
                    extracted_data["tables"] = pdf_tables
                    adapter = PDFSemanticAdapter(filename, cy_year)
                    facts = adapter.adapt(extracted_data)
                    return facts, {"title": filename, "fiscal_year": cy_year, "source": "pdfplumber_tables", "tables": pdf_tables}
            except (ImportError, RuntimeError, ValueError) as e:
                logger.warning(f"pdfplumber table extraction failed: {e}. Falling back to line heuristics.")

        # Attempt table extraction for HTML content for higher precision
        if not is_pdf and not is_image:
            html_tables = _extract_tables_from_html(content, global_scale=global_scale)
            if html_tables:
                extracted_data["tables"].extend(html_tables)
            else:
                try:
                    from .render_adapter import render_html_to_html_async
                    rendered_html = await render_html_to_html_async(content)
                    html_tables = _extract_tables_from_html(rendered_html.encode("utf-8"), global_scale=global_scale)
                    if html_tables:
                        extracted_data["tables"].extend(html_tables)
                except (ImportError, RuntimeError, ValueError):
                    logger.warning("HTML render fallback failed", exc_info=True)
        
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
                    val_dec = Decimal(clean_str)
                    if 1990 <= val_dec <= 2030 and val_dec == int(val_dec) and '.' not in match.group(0): continue
                    if is_negative: val_dec = -val_dec

                    # [Step 3] Global Unit Lock for Unstructured Data
                    # Normalize to Billions ($B)
                    val_scaled = val_dec
                    
                    if 'eps' not in label_text.lower() and 'per share' not in label_text.lower():
                        if global_scale >= 1_000_000_000.0: # Billions
                            val_scaled = val_dec
                        elif global_scale >= 1_000_000.0: # Millions
                             val_scaled = val_dec / Decimal("1000")
                        else: # Ones
                             val_scaled = val_dec / Decimal("1000000000")
                        
                        # Boeing Rule / Outlier Check
                        threshold = Decimal("10000")
                        if 'share' in label_text.lower() or 'volume' in label_text.lower():
                            threshold = Decimal("100000")

                        if abs(val_scaled) > threshold:
                             while abs(val_scaled) > threshold:
                                 val_scaled /= Decimal("1000")

                    valid_nums.append(str(val_scaled))
                except (InvalidOperation, ValueError):
                    continue

            if len(valid_nums) >= 2: extracted_data["tables"][0]["rows"].append([label_text, valid_nums[-2], valid_nums[-1]])
            elif len(valid_nums) == 1: extracted_data["tables"][0]["rows"].append([label_text, valid_nums[0], ""])
        
        adapter = PDFSemanticAdapter(filename, cy_year)
        facts = adapter.adapt(extracted_data)
        result = {
            "title": filename,
            "fiscal_year": cy_year,
            "source": "Enhanced Full-Row Parser",
            "tables": extracted_data.get("tables", []),
            "key_metrics": extracted_data.get("key_metrics", {}),
            "needs_review": False,
        }
        if not facts:
            result["needs_review"] = True
        return facts, result


async def _extract_text_from_html_async(content: bytes) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        for tag in soup.find_all(['tr', 'p', 'div', 'h1', 'h2', 'h3', 'br', 'li']):
            tag.insert_after('\n')
        for tag in soup.find_all(['td', 'th']):
            tag.insert_after(' ')
        text = soup.get_text()
        if text and len(text.strip()) > 50:
            return text
    except (ImportError, AttributeError, ValueError, OSError) as exc:
        logger.debug("HTML parse via BeautifulSoup failed: %s", exc)

    # Fallback: render with Playwright for JS-heavy HTML
    try:
        from .render_adapter import render_html_to_text_async
        rendered_text = await render_html_to_text_async(content)
        if rendered_text and len(rendered_text.strip()) > 50:
            return rendered_text
    except (ImportError, AttributeError, RuntimeError, ValueError) as exc:
        logger.debug("HTML render adapter failed: %s", exc)

    text = content.decode(errors='ignore')
    text = re.sub(r'<(script|style)[^>]*>.*?</\\1>', ' ', text, flags=re.S|re.I)
    text = re.sub(r'<br\\s*/?>', '\\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\\s+', ' ', text)
    return unescape(text)


def _extract_tables_from_html(content: bytes, *, global_scale: float) -> List[Dict[str, Any]]:
    """
    Extract HTML tables without pandas to avoid heavy/fragile dependencies.
    Applies the same "billions" scaling convention as the PDF path when the
    document indicates figures are in millions.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    import re
    from decimal import Decimal, InvalidOperation

    html = content.decode(errors="ignore")
    # Prefer local (document) hints over the caller's global guess.
    scale_hint = global_scale
    if re.search(r"(?:in\\s+)?millions?", html, re.IGNORECASE):
        scale_hint = 1_000_000.0
    elif re.search(r"(?:in\\s+)?billions?", html, re.IGNORECASE):
        scale_hint = 1_000_000_000.0

    def scale_to_billions(val: Decimal) -> Decimal:
        if scale_hint >= 1_000_000_000.0:
            return val
        if scale_hint >= 1_000_000.0:
            return val / Decimal("1000")
        if abs(val) >= Decimal("1000"):
            return val / Decimal("1000")
        return val / Decimal("1000000000")

    def maybe_scale(cell_text: str, *, label_hint: str) -> str:
        raw = (cell_text or "").strip()
        if raw == "":
            return raw
        # Skip EPS/ratios.
        if any(k in (label_hint or "").lower() for k in ("eps", "per share", "margin", "ratio", "%")):
            return raw
        m = re.fullmatch(r"-?\(?[\d,]+(?:\.\d+)?\)?", raw)
        if not m:
            return raw
        s = raw.replace(",", "").strip()
        neg = False
        if s.startswith("(") and s.endswith(")"):
            neg = True
            s = s[1:-1]
        if s.startswith("-"):
            neg = True
            s = s[1:]
        try:
            d = Decimal(s)
        except (InvalidOperation, ValueError):
            return raw
        if neg:
            d = -d
        return str(scale_to_billions(d))

    soup = BeautifulSoup(html, "lxml")

    results: List[Dict[str, Any]] = []
    for idx, table in enumerate(soup.find_all("table")):
        rows: List[List[str]] = []
        header_row = None

        thead = table.find("thead")
        if thead:
            tr = thead.find("tr")
            if tr:
                header_row = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]

        if not header_row:
            first_tr = table.find("tr")
            if first_tr:
                header_row = [c.get_text(" ", strip=True) for c in first_tr.find_all(["th", "td"])]

        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if not cells:
                continue
            row = [c.get_text(" ", strip=True) for c in cells]
            if header_row and row == header_row:
                continue
            rows.append(row)

        if not header_row or len(header_row) < 2 or not rows:
            continue

        # Normalize row widths.
        width = len(header_row)
        norm_rows: List[List[str]] = []
        for r in rows:
            if len(r) < width:
                r = r + [""] * (width - len(r))
            elif len(r) > width:
                r = r[:width]
            norm_rows.append(r)

        # Apply scaling to numeric cells.
        scaled_rows: List[List[str]] = []
        for r in norm_rows:
            label_hint = r[0] if r else ""
            scaled_rows.append([r[0]] + [maybe_scale(c, label_hint=label_hint) for c in r[1:]])

        results.append({
            "name": f"HTML Table {idx + 1}",
            "headers": header_row,
            "rows": scaled_rows,
        })

    return results


def _extract_text_from_image(content: bytes) -> str:
    try:
        from PIL import Image
        import pytesseract
        import io as _io
        img = Image.open(_io.BytesIO(content))
        return pytesseract.image_to_string(img)
    except (ImportError, AttributeError, RuntimeError, ValueError) as e:
        logger.warning(f"Image OCR not available: {e}")
    return ""


def _extract_tables_from_pdf(content: bytes, *, cy_year: str, py_year: str, global_scale: float) -> List[Dict[str, Any]]:
    """
    Extract statement-like tables from a PDF using pdfplumber.

    Goal: produce deterministic rows of [Metric, CY, PY] for downstream PDFSemanticAdapter.
    The extracted numeric values are scaled to match FinDistill's "billions" convention:
    - "in millions" -> divide by 1,000
    - "in billions" -> keep as-is
    - otherwise -> divide by 1e9 (best-effort)
    """
    import io
    import re
    from decimal import Decimal, InvalidOperation

    try:
        import pdfplumber
    except (ImportError, AttributeError, RuntimeError, ValueError) as e:
        raise RuntimeError(f"pdfplumber not available: {e}")

    def is_statement_line(label: str) -> bool:
        s = (label or "").strip().lower()
        if not s:
            return False
        # hard negatives
        negatives = [
            "item ", "risk factors", "controls and procedures", "table of contents", "part i", "part ii",
            "washington", "commission", "pursuant", "telephone", "suite", "address", "zip", "file no",
        ]
        if any(n in s for n in negatives):
            return False
        # require at least one strong financial keyword
        positives = [
            "revenue", "sales", "income", "earnings", "profit", "loss", "expense", "cost",
            "assets", "liabilities", "equity", "cash", "debt", "interest", "dividend",
            "operating", "investing", "financing", "receivable", "payable", "inventory",
        ]
        return any(p in s for p in positives)

    def scale_to_billions(val: Decimal, *, scale_hint: float) -> Decimal:
        """
        Convert statement figures into the engine's "billions" convention.

        If scale is unknown, we use a deterministic heuristic:
        - values >= 1,000 are usually "in millions" statement figures
        - otherwise treat as raw currency and convert to billions
        """
        if scale_hint >= 1_000_000_000.0:
            return val
        if scale_hint >= 1_000_000.0:
            return val / Decimal("1000")
        if abs(val) >= Decimal("1000"):
            return val / Decimal("1000")
        return val / Decimal("1000000000")

    def extract_numbers(text: str) -> tuple[str, List[Decimal]]:
        # Returns (label, numbers) using the first N numeric columns in the line.
        raw = (text or "").strip()
        if not raw:
            return ("", [])
        matches = list(re.finditer(r"(-?\(?[\d,]+(?:\.\d+)?\)?)", raw))
        if len(matches) < 2:
            return (raw, [])
        first = matches[0]
        label = raw[: first.start()].strip()
        label = label.replace("$", "").strip(": ").strip()
        def to_dec(s: str) -> Optional[Decimal]:
            s = s.replace(",", "").replace("$", "").strip()
            neg = False
            if s.startswith("(") and s.endswith(")"):
                neg = True
                s = s[1:-1]
            if s.startswith("-"):
                neg = True
                s = s[1:]
            try:
                d = Decimal(s)
                return -d if neg else d
            except (InvalidOperation, ValueError):
                return None
        numbers: List[Decimal] = []
        for m in matches:
            val = to_dec(m.group(0))
            if val is None:
                continue
            numbers.append(val)
        return (label, numbers)

    tables_out: List[Dict[str, Any]] = []

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        # Focus around where financial statements usually sit, but keep a safe cap.
        page_indices = list(range(min(len(pdf.pages), 80)))
        for i in page_indices:
            page = pdf.pages[i]
            # Prefer page-local scaling hints when available.
            page_text = page.extract_text() or ""
            page_scale = global_scale
            if re.search(r"(?:in\\s+)?millions?", page_text, re.IGNORECASE):
                page_scale = 1_000_000.0
            elif re.search(r"(?:in\\s+)?billions?", page_text, re.IGNORECASE):
                page_scale = 1_000_000_000.0
            extracted = page.extract_tables() or []
            if not extracted:
                continue
            rows_out: List[List[str]] = []
            max_cols = 0
            for t in extracted:
                for row in t or []:
                    if not row:
                        continue
                    # Many PDFs collapse into a single cell row; join non-empty cells.
                    joined = " ".join([c for c in row if c and str(c).strip()])
                    if not joined:
                        continue
                    label, numbers = extract_numbers(joined)
                    if len(numbers) < 2:
                        continue
                    if not is_statement_line(label):
                        continue
                    # Keep all numeric columns to preserve multi-year tables.
                    scaled = [str(scale_to_billions(v, scale_hint=page_scale)) for v in numbers]
                    max_cols = max(max_cols, len(scaled))
                    rows_out.append([label] + scaled)

            if len(rows_out) >= 8:
                # Derive header years from page text when possible.
                years = re.findall(r"20\d{2}", page_text)
                years = [y for y in years if 1990 <= int(y) <= 2035]
                uniq: List[str] = []
                for y in years:
                    if y not in uniq:
                        uniq.append(y)
                uniq.sort(reverse=True)
                if max_cols <= 0:
                    max_cols = max(len(r) for r in rows_out) - 1
                if len(uniq) >= max_cols:
                    header_years = uniq[:max_cols]
                else:
                    # Fallback ordering: CY, PY, PY-1
                    header_years = [cy_year, py_year]
                    for _ in range(len(header_years), max_cols):
                        try:
                            header_years.append(str(int(header_years[-1]) - 1))
                        except (ValueError, TypeError):
                            header_years.append(f"{py_year}_prev")

                # Normalize row widths to match headers.
                target_len = 1 + max_cols
                normalized_rows: List[List[str]] = []
                for row in rows_out:
                    if len(row) < target_len:
                        row = row + [""] * (target_len - len(row))
                    elif len(row) > target_len:
                        row = row[:target_len]
                    normalized_rows.append(row)
                tables_out.append({
                    "name": f"PDF Table p{i+1}",
                    "headers": ["Metric"] + header_years[:max_cols],
                    "rows": normalized_rows,
                })

    return tables_out


async def _extract_text_from_image_async(content: bytes) -> str:
    """
    Prefer Google Vision (if configured), then fall back to local OCR (pytesseract).
    """
    # 1) Google Vision (API key)
    try:
        if os.getenv("GOOGLE_VISION_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            from .google_vision_ocr import ocr_image_bytes
            text = await ocr_image_bytes(content)
            if text and len(text.strip()) > 10:
                return text
    except (ImportError, RuntimeError, ValueError) as exc:
        logger.warning("Vision OCR failed, falling back: %s", exc)

    # 2) Local OCR fallback (optional): when Vision is configured but fails/limits, prefer returning empty
    # so the caller can fall back to deterministic parsers instead of noisy OCR.
    if os.getenv("ALLOW_LOCAL_OCR_FALLBACK", "0") == "1":
        return _extract_text_from_image(content)
    return ""


async def _extract_text_from_pdf_images_async(content: bytes, *, max_pages: Optional[int] = None) -> str:
    """
    Render PDF pages to images and OCR them.

    Prefer Google Vision if configured. If not configured, fall back to local OCR.
    Uses pypdfium2 when available (no poppler dependency).
    """
    images = []
    # Render with pypdfium2 (preferred)
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(io.BytesIO(content))
        if max_pages is None:
            max_pages = int(os.getenv("PDF_OCR_MAX_PAGES", "6") or "6")
        max_pages = max(1, min(int(max_pages), 12))
        page_count = min(len(pdf), int(max_pages))
        for i in range(page_count):
            page = pdf[i]
            # deterministic rendering params
            pil = page.render(scale=2.2).to_pil()
            images.append(pil)
    except (ImportError, RuntimeError, ValueError, OSError) as e:
        logger.warning(f"pypdfium2 render unavailable/failed: {e}. Trying pdf2image.")

    # Fallback render with pdf2image (requires poppler)
    if not images:
        try:
            from pdf2image import convert_from_bytes
            if max_pages is None:
                max_pages = int(os.getenv("PDF_OCR_MAX_PAGES", "6") or "6")
            max_pages = max(1, min(int(max_pages), 12))
            images = convert_from_bytes(content, dpi=250, first_page=1, last_page=int(max_pages))
        except (ImportError, RuntimeError, ValueError, OSError) as e:
            logger.warning(f"pdf2image render unavailable/failed: {e}")
            images = []

    if not images:
        return ""

    # OCR path
    try:
        if os.getenv("GOOGLE_VISION_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            from .google_vision_ocr import ocr_pil_images
            text = await ocr_pil_images(images)
            if text and len(text.strip()) > 10:
                return text
    except (ImportError, RuntimeError, ValueError, OSError) as e:
        logger.warning(f"Google Vision PDF OCR failed: {e}")

    # Local OCR fallback (optional).
    if os.getenv("ALLOW_LOCAL_OCR_FALLBACK", "0") == "1":
        try:
            from .ocr_adapter import extract_text_from_images
            return extract_text_from_images(images)
        except (ImportError, RuntimeError, ValueError, OSError) as e:
            logger.warning(f"PDF image OCR not available: {e}")
            return ""
    return ""
