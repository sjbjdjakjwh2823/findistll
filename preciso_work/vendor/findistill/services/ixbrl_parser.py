import re
import logging
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from .xbrl_semantic_engine import SemanticFact, UnitManager, ScaleProcessor

logger = logging.getLogger(__name__)

class IXBRLParser:
    """
    Parses Inline XBRL (HTML/XHTML) files to extract financial facts.
    Maps extracted data to SemanticFact objects for the XBRLSemanticEngine.
    v16.0: Integration with ScaleProcessor for Arithmetic Self-Healing and Unit Locking.
    """
    
    def __init__(self, file_content: bytes):
        from bs4 import XMLParsedAsHTMLWarning
        import warnings
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        
        self.soup = BeautifulSoup(file_content, "lxml")
        self.namespaces = {}
        self.contexts = {} # ID -> Date/Period
        self.units = {}    # ID -> Unit Type
        
    def parse(self) -> List[SemanticFact]:
        """Main execution method."""
        try:
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
            text_content = unit.get_text().lower()
            
            if "usd" in text_content or "$" in text_content:
                self.units[u_id] = "currency"
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
        non_fractions = self.soup.find_all(re.compile(r'ix:nonfraction', re.IGNORECASE))
        
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
                    
                # Clean Value logic integrated into ScaleProcessor, but we need raw string for it.
                # However, ScaleProcessor expects 'raw_val' string.
                # iXBRL 'scale' attribute must be applied BEFORE ScaleProcessor normalization?
                # ScaleProcessor logic: clean_val -> Decimal -> normalize_to_billion.
                # If we apply scale here, we get a Decimal.
                
                # Handling Scale attribute manually first
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
                
                if scale:
                    try:
                        scale_int = int(scale)
                        val_decimal = val_decimal * (Decimal(10) ** scale_int)
                    except: pass
                
                # Now convert back to string or pass decimal? 
                # ScaleProcessor.apply_self_healing takes string `raw_val` and does cleanup.
                # But we already have a Decimal `val_decimal` that represents the TRUE value from iXBRL.
                # We should bypass the string cleanup in ScaleProcessor and use the logic directly or format it.
                # Let's pass the string of the *scaled* value to ScaleProcessor.
                
                scaled_raw_val = str(val_decimal)
                
                # Determine Unit Type
                unit_type = self.units.get(unit_ref, "currency")
                
                # v16.0 Integration: Call ScaleProcessor
                dec_int = int(decimals) if decimals else None
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
                    confidence_score=conf_score
                )
                if tag != "raw_pass":
                    fact.tags.append(tag)
                    
                facts.append(fact)
                
            except Exception as e:
                continue
                
        return facts

    def get_metadata(self) -> Dict[str, str]:
        """Attempts to extract Entity Name and Fiscal Year."""
        meta = {"company": "Unknown Entity", "year": "Unknown Year"}
        
        # In iXBRL, metadata is often in <ix:nonNumeric name="dei:EntityRegistrantName" ...>
        # We need to scan tags with 'name' attributes.
        
        # 1. Scan ix:nonNumeric tags
        non_numerics = self.soup.find_all(re.compile(r'ix:nonnumeric', re.IGNORECASE))
        
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
            pass
            
        return meta
