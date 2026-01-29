
import os
import re
from lxml import etree
import logging

logger = logging.getLogger(__name__)

class XBRLParser:
    """
    Lightweight XBRL/XML Parser for FinDistill.
    Extracts key financial metrics from raw XML/XBRL files.
    """
    def __init__(self):
        self.namespaces = {
            'xbrli': 'http://www.xbrl.org/2003/instance',
            'link': 'http://www.xbrl.org/2003/linkbase',
            'xlink': 'http://www.w3.org/1999/xlink',
            'us-gaap': 'http://fasb.org/us-gaap/2021-01-31', # Example NS, will detect dynamically
            'ifrs-full': 'http://xbrl.ifrs.org/taxonomy/2021-03-24/ifrs-full',
        }

    def parse_file(self, file_path):
        """Parse a single local XML/XBRL file and return a dictionary of facts."""
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {}

        try:
            tree = etree.parse(file_path)
            root = tree.getroot()
            
            # Update namespaces from root
            if root.nsmap:
                # Filter None keys which lxml might produce
                clean_ns = {k: v for k, v in root.nsmap.items() if k}
                self.namespaces.update(clean_ns)
            
            # Strategy 1: Find all 'facts' (elements with contextRef)
            # This covers us-gaap:*, ifrs-full:*, etc.
            facts = {}
            
            # Iterate all elements to find those with 'contextRef'
            for elem in root.iter():
                context_ref = elem.get('contextRef')
                if context_ref:
                    # It's a fact!
                    # Tag name includes namespace, e.g., {http://fasb.org...}Assets
                    # We want just 'Assets'
                    tag = etree.QName(elem).localname
                    value = elem.text
                    
                    # Store latest value (simplified logic)
                    # In a real engine, we'd parse context dates to sort properly.
                    if value and value.strip():
                        try:
                            # Clean numeric value
                            val_clean = float(value.strip())
                            facts[tag] = val_clean
                        except ValueError:
                            # Not a number (text block?), save as is
                            facts[tag] = value.strip()
                            
            # Strategy 2: If standard tags missing, try text search (fallback for messy XML)
            if not facts:
                logger.warning(f"No XBRL contextRefs found in {file_path}. Trying regex fallback...")
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Regex for common patterns: <ns:Tag ...>Value</ns:Tag>
                    patterns = [
                        r'([A-Z][a-zA-Z]+)Current',
                        r'([A-Z][a-zA-Z]+)Noncurrent',
                        r'([A-Z][a-zA-Z]+)Assets',
                        r'([A-Z][a-zA-Z]+)Liabilities',
                        r'([A-Z][a-zA-Z]+)Equity',
                        r'([A-Z][a-zA-Z]+)Revenue',
                        r'([A-Z][a-zA-Z]+)Income',
                    ]
                    # This is very rough, just to get *something* for demo
                    pass

            return self._normalize_metrics(facts)

        except Exception as e:
            logger.error(f"Error parsing XBRL {file_path}: {e}")
            return {}

    def _normalize_metrics(self, raw_facts):
        """Map raw XBRL tags to standard FinDistill schema."""
        schema = {
            "Revenues": ["Revenue", "Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax"],
            "NetIncome": ["NetIncomeLoss", "ProfitLoss", "NetIncome"],
            "Assets": ["Assets", "AssetsCurrent", "AssetsNoncurrent"],
            "Liabilities": ["Liabilities", "LiabilitiesCurrent", "LiabilitiesNoncurrent"],
            "Equity": ["StockholdersEquity", "Equity"],
            "EPS": ["EarningsPerShareBasic", "EarningsPerShareDiluted"]
        }
        
        normalized = {}
        for key, aliases in schema.items():
            for alias in aliases:
                # Check for direct match or partial match in raw keys
                matches = [v for k, v in raw_facts.items() if alias in k]
                if matches:
                    # Pick the largest value (heuristic for 'Total' vs 'Current')
                    # Or just the first found
                    numeric_matches = [m for m in matches if isinstance(m, (int, float))]
                    if numeric_matches:
                        normalized[key] = max(numeric_matches) # Max usually means Total
                        break
        
        # Calculate derived ratios if possible
        if "NetIncome" in normalized and "Revenues" in normalized and normalized["Revenues"] > 0:
            normalized["NetMargin"] = normalized["NetIncome"] / normalized["Revenues"]
            
        return normalized

