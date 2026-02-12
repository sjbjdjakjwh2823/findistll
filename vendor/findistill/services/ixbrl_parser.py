import re
import logging
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional
from .xbrl_semantic_engine import SemanticFact, UnitManager, ScaleProcessor

logger = logging.getLogger(__name__)

class IXBRLParser:
    """
    Parses Inline XBRL (HTML/XHTML) files to extract financial facts.
    Maps extracted data to SemanticFact objects for the XBRLSemanticEngine.
    v16.0: Integration with ScaleProcessor for Arithmetic Self-Healing and Unit Locking.
    """
    
    def __init__(self, file_content: bytes):
        self.soup = None
        self._raw = file_content.decode(errors="ignore")
        try:
            from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
            import warnings
            warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
            self.soup = BeautifulSoup(file_content, "lxml")
        except (ImportError, RuntimeError, ValueError) as e:
            logger.warning(f"BeautifulSoup not available; iXBRL parse disabled: {e}")
        self.namespaces = {}
        self.contexts = {} # ID -> Date/Period
        self.units = {}    # ID -> Unit Type
        self.unit_currency = {}  # ID -> currency code (e.g., USD)
        
    def parse(self) -> List[SemanticFact]:
        """Main execution method."""
        try:
            if self.soup is None:
                self._parse_contexts_regex()
                self._parse_units_regex()
                facts = self._extract_numeric_facts_regex()
                logger.info("iXBRL Parser (regex): Extracted %s facts.", len(facts))
                return facts
            # 1. Extract Contexts (Dates)
            self._parse_contexts()
            
            # 2. Extract Units
            self._parse_units()
            
            # 3. Extract Numeric Facts (ix:nonFraction)
            facts = self._extract_numeric_facts()
            
            logger.info(f"iXBRL Parser: Extracted {len(facts)} facts.")
            return facts
            
        except Exception as e:
            logger.error(f"iXBRL Parsing Error: {e}")
            raise

    def _parse_contexts_regex(self) -> None:
        """
        Regex fallback for contexts when BeautifulSoup is unavailable.
        """
        ctx_pattern = re.compile(r"<[^>]*context[^>]*id=[\"']([^\"']+)[\"'][^>]*>(.*?)</[^>]*context>", re.IGNORECASE | re.DOTALL)
        for match in ctx_pattern.finditer(self._raw or ""):
            ctx_id = match.group(1)
            body = match.group(2)
            if not ctx_id:
                continue
            date_str = None
            end_m = re.search(r"<[^>]*endDate[^>]*>([^<]+)</[^>]*endDate>", body, re.IGNORECASE)
            if end_m:
                date_str = end_m.group(1).strip()
            else:
                inst_m = re.search(r"<[^>]*instant[^>]*>([^<]+)</[^>]*instant>", body, re.IGNORECASE)
                if inst_m:
                    date_str = inst_m.group(1).strip()
            if date_str:
                self.contexts[ctx_id] = date_str

    def _parse_units_regex(self) -> None:
        """
        Regex fallback for units when BeautifulSoup is unavailable.
        """
        unit_pattern = re.compile(r"<[^>]*unit[^>]*id=[\"']([^\"']+)[\"'][^>]*>(.*?)</[^>]*unit>", re.IGNORECASE | re.DOTALL)
        for match in unit_pattern.finditer(self._raw or ""):
            unit_id = match.group(1)
            body = match.group(2)
            if not unit_id:
                continue
            raw_text = body or ""
            m = re.search(r"iso4217:([a-zA-Z]{3})", raw_text)
            if m:
                self.unit_currency[unit_id] = m.group(1).upper()
            text_content = raw_text.lower()
            if "usd" in text_content or "$" in text_content:
                self.units[unit_id] = "currency"
                self.unit_currency.setdefault(unit_id, "USD")
            elif "share" in text_content:
                self.units[unit_id] = "shares"
            elif "pure" in text_content or "rate" in text_content:
                self.units[unit_id] = "ratio"
            else:
                self.units[unit_id] = "currency"

    def _extract_numeric_facts_regex(self) -> List[SemanticFact]:
        """
        Regex fallback for ix:nonFraction parsing when BeautifulSoup is unavailable.
        """
        facts: List[SemanticFact] = []
        if not self._raw:
            return facts

        tag_pattern = re.compile(
            r"<(?P<tag>[^>]*nonFraction[^>]*)>(?P<value>.*?)</[^>]*nonFraction>",
            re.IGNORECASE | re.DOTALL,
        )
        for match in tag_pattern.finditer(self._raw):
            tag = match.group("tag") or ""
            raw_text = (match.group("value") or "").strip()
            if not raw_text:
                continue

            def _attr(name: str) -> Optional[str]:
                m = re.search(rf"{name}\s*=\s*['\"]([^'\"]+)['\"]", tag, re.IGNORECASE)
                return m.group(1) if m else None

            concept_raw = (_attr("name") or "").split(":")[-1]
            context_ref = _attr("contextRef") or _attr("contextref")
            unit_ref = _attr("unitRef") or _attr("unitref")
            decimals = _attr("decimals")
            scale = _attr("scale")
            sign = _attr("sign")
            format_attr = _attr("format")

            if not context_ref or context_ref not in self.contexts:
                continue

            clean_val_str = re.sub(r"[^\d.]", "", raw_text)
            if not clean_val_str:
                continue
            try:
                val_decimal = Decimal(clean_val_str)
            except (InvalidOperation, ValueError):
                continue

            if sign and "-" in sign:
                val_decimal *= -1

            dec_int = int(decimals) if decimals else None
            if scale:
                try:
                    scale_int = int(scale)
                    val_decimal = val_decimal * (Decimal(10) ** scale_int)
                except (InvalidOperation, ValueError):
                    logger.debug("iXBRL scale parse failed", exc_info=True)
            else:
                if dec_int is not None and dec_int < 0:
                    try:
                        val_decimal = val_decimal * (Decimal(10) ** (-dec_int))
                    except (InvalidOperation, ValueError):
                        logger.debug("iXBRL decimals scale failed", exc_info=True)

            scaled_raw_val = str(val_decimal)

            unit_type = self.units.get(unit_ref, "currency")
            currency = self.unit_currency.get(unit_ref) if unit_type == "currency" else None

            scaled_val, tag, confidence = ScaleProcessor.apply_self_healing(
                scaled_raw_val,
                dec_int,
                unit_type,
            )

            concept = re.sub(r"[^a-zA-Z0-9]", "", concept_raw or "unknown")
            raw_date = self.contexts.get(context_ref)

            fact = SemanticFact(
                concept=concept,
                label=concept_raw or concept,
                value=scaled_val,
                raw_value=raw_text,
                unit=unit_type,
                period=raw_date or "Unknown",
                context_ref=context_ref,
                decimals=dec_int,
                is_consolidated=True,
                dimensions=({"currency": currency} if currency else None),
                confidence_score=confidence,
            )
            if tag != "raw_pass":
                fact.tags.append(tag)
            facts.append(fact)

        return facts

    def _parse_contexts(self):
        """Finds xbrli:context or standard context tags hidden in ix:resources."""
        # Search for context tags. They might be namespaced like xbrli:context or just context
        # BS4 handles namespaces by converting to tag names like "xbrli:context"
        
        ctx_tags = self.soup.find_all(re.compile(r'.*context$'))
        
        for ctx in ctx_tags:
            c_id = ctx.get("id")
            if not c_id:
                continue
                
            # Find Period -> EndDate or Instant
            period = ctx.find(re.compile(r'.*period$'))
            if not period:
                continue
                
            date_str = "Unknown"
            
            # Try EndDate
            end_date = period.find(re.compile(r'.*endDate$'))
            if end_date:
                date_str = end_date.get_text().strip()
            else:
                # Try Instant
                instant = period.find(re.compile(r'.*instant$'))
                if instant:
                    date_str = instant.get_text().strip()
            
            # Map ID to Date
            if date_str != "Unknown":
                self.contexts[c_id] = date_str

    def _parse_units(self):
        """Finds xbrli:unit tags."""
        unit_tags = self.soup.find_all(re.compile(r'.*unit$'))
        
        for unit in unit_tags:
            u_id = unit.get("id")
            if not u_id:
                continue
                
            # Determine type
            # Check for <measure>iso4217:USD</measure> or similar
            raw_text = unit.get_text() or ""
            text_content = raw_text.lower()
            # Capture ISO currency if present.
            m = re.search(r"iso4217:([a-zA-Z]{3})", raw_text)
            if m:
                self.unit_currency[u_id] = m.group(1).upper()
            
            if "usd" in text_content or "$" in text_content:
                self.units[u_id] = "currency"
                self.unit_currency.setdefault(u_id, "USD")
            elif "share" in text_content:
                self.units[u_id] = "shares"
            elif "pure" in text_content or "rate" in text_content:
                self.units[u_id] = "ratio"
            else:
                self.units[u_id] = "currency" # Default

    def _extract_numeric_facts(self) -> List[SemanticFact]:
        """Extracts ix:nonFraction elements."""
        facts = []
        
        # Find all numeric tags
        # Namespace prefixes vary (ix:nonFraction, ixbrl:nonFraction, etc).
        # Match by suffix to be robust across parsers.
        non_fractions = self.soup.find_all(re.compile(r'.*nonfraction$', re.IGNORECASE))
        
        for nf in non_fractions:
            try:
                # Attributes
                concept_raw = nf.get("name", "").split(":")[-1] # Remove prefix like us-gaap:
                context_ref = nf.get("contextref")
                unit_ref = nf.get("unitref")
                decimals = nf.get("decimals")
                scale = nf.get("scale")
                sign = nf.get("sign") # usually "-" for negative
                format_attr = nf.get("format") # e.g., ixt:num-dot-decimal
                
                # Validation
                if not context_ref or context_ref not in self.contexts:
                    continue
                    
                # Extract Text Value
                raw_text = nf.get_text().strip()
                if not raw_text:
                    continue
                clean_str = raw_text.strip()
                lower_clean = clean_str.lower()
                # Guard: ISO-8601 durations and enumerations/URIs are not numeric facts.
                if re.match(r"^P(?!\\d{4}-\\d{2}-\\d{2})([0-9]+Y)?([0-9]+M)?([0-9]+D)?(T.*)?$", clean_str):
                    continue
                if "http://" in lower_clean or "https://" in lower_clean or "://" in lower_clean:
                    continue
                
                # Clean Value logic integrated into ScaleProcessor, but we need raw string for it.
                # However, ScaleProcessor expects 'raw_val' string.
                # iXBRL 'scale' attribute must be applied BEFORE ScaleProcessor normalization?
                # ScaleProcessor logic: clean_val -> Decimal -> normalize_to_billion.
                # If we apply scale here, we get a Decimal.
                
                # Handling Scale/Decimals attributes:
                # - Some iXBRL filings omit `scale` but rely on negative `decimals` (e.g., -6) to indicate
                #   the reported number is in millions. In those cases, reconstruct full dollars first.
                clean_val_str = re.sub(r'[^\d.]', '', raw_text)
                if not clean_val_str: continue
                val_decimal = Decimal(clean_val_str)
                
                if sign and "-" in sign: val_decimal *= -1
                
                # IMPORTANT: Apply iXBRL 'scale' attribute (e.g. scale="6" means millions)
                # If we apply this, we get the 'real' value (e.g. 50 * 10^6 = 50,000,000).
                # Then ScaleProcessor will normalize 50,000,000 -> 0.05 Billion.
                # WAIT. If scale is 6, value is Millions.
                # ScaleProcessor logic checks "if > 1000 => divide by 1000".
                # 50,000,000 normalized to billion is 0.05. This is < 0.0001 check? No 0.05 > 0.0001.
                # 5,000,000,000 (5B) -> normalized 5.0. Correct.
                
                dec_int = int(decimals) if decimals else None

                if scale:
                    try:
                        scale_int = int(scale)
                        val_decimal = val_decimal * (Decimal(10) ** scale_int)
                    except Exception:
                        logger.debug("iXBRL scale parse failed (alt path)", exc_info=True)
                else:
                    # If decimals is negative (e.g., -6), values are typically reported in millions.
                    # Reconstruct full dollars before normalizing to billions.
                    if dec_int is not None and dec_int < 0:
                        try:
                            val_decimal = val_decimal * (Decimal(10) ** (-dec_int))
                        except Exception:
                            logger.debug("iXBRL decimals scale failed (alt path)", exc_info=True)
                
                # Now convert back to string or pass decimal? 
                # ScaleProcessor.apply_self_healing takes string `raw_val` and does cleanup.
                # But we already have a Decimal `val_decimal` that represents the TRUE value from iXBRL.
                # We should bypass the string cleanup in ScaleProcessor and use the logic directly or format it.
                # Let's pass the string of the *scaled* value to ScaleProcessor.
                
                scaled_raw_val = str(val_decimal)
                
                # Determine Unit Type
                unit_type = self.units.get(unit_ref, "currency")
                currency = self.unit_currency.get(unit_ref) if unit_type == "currency" else None
                
                # v16.0 Integration: Call ScaleProcessor
                final_val, tag, conf_score = ScaleProcessor.apply_self_healing(scaled_raw_val, dec_int, unit_type)
                
                # Normalize Concept Name
                concept = re.sub(r'[^a-zA-Z0-9]', '', concept_raw)
                
                raw_date = self.contexts[context_ref]
                
                fact = SemanticFact(
                    concept=concept,
                    label=concept_raw, # Use raw name as label
                    value=final_val,
                    raw_value=raw_text,
                    unit=unit_type,
                    period=raw_date, # Passing RAW DATE. Ingestion logic maps this.
                    context_ref=context_ref,
                    decimals=dec_int,
                    is_consolidated=True,
                    dimensions=({"currency": currency} if currency else None),
                    confidence_score=conf_score
                )
                if tag != "raw_pass":
                    fact.tags.append(tag)
                    
                facts.append(fact)
                
            except Exception as e:
                logger.debug("iXBRL numeric fact parse failed", exc_info=True)
                continue
                
        return facts

    def get_metadata(self) -> Dict[str, str]:
        """Attempts to extract Entity Name and Fiscal Year."""
        meta = {"company": "Unknown Entity", "year": "Unknown Year"}
        if self.soup is None:
            return meta
        
        # In iXBRL, metadata is often in <ix:nonNumeric name="dei:EntityRegistrantName" ...>
        # We need to scan tags with 'name' attributes.
        
        # 1. Scan ix:nonNumeric tags
        non_numerics = self.soup.find_all(re.compile(r'.*nonnumeric$', re.IGNORECASE))
        
        for tag in non_numerics:
            name_attr = tag.get("name", "")
            
            # Entity Name
            if "EntityRegistrantName" in name_attr:
                meta["company"] = tag.get_text().strip()
                
            # Fiscal Year Focus (e.g. 2023)
            elif "DocumentFiscalYearFocus" in name_attr:
                meta["year"] = tag.get_text().strip()
                
            # Document Period End Date (e.g. 2023-09-30) - as fallback for year
            elif "DocumentPeriodEndDate" in name_attr and meta["year"] == "Unknown Year":
                text = tag.get_text().strip()
                # Extract year from YYYY-MM-DD
                match = re.search(r'(\d{4})', text)
                if match:
                    meta["year"] = match.group(1)
        
        # Fallback: Hidden XBRL might use pure XML tags if not inline (unlikely for iXBRL files but possible)
        if meta["company"] == "Unknown Entity":
            # Try naive text search or original logic just in case
            logger.debug("iXBRL metadata fallback not implemented; leaving Unknown Entity")
            
        return meta
