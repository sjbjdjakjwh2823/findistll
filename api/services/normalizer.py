"""
FinDistill Financial Data Normalizer

Normalizes financial data for consistency:
- Financial term spell-checking
- Currency unification (KRW/USD)
- Date format standardization
- Number format normalization
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime


class FinancialNormalizer:
    """Normalizes financial data for AI training consistency."""
    
    # Common financial term corrections (English)
    TERM_CORRECTIONS = {
        "Reveneu": "Revenue",
        "Net Incom": "Net Income",
        "Assetts": "Assets",
        "Liablities": "Liabilities",
        "Equitry": "Equity",
        "Operatin Income": "Operating Income",
    }
    
    # Date format patterns
    DATE_PATTERNS = [
        (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', r'\1-\2-\3'),  # 2024.1.1 -> 2024-1-1
        (r'(\d{4})/(\d{1,2})/(\d{1,2})', r'\1-\2-\3'),   # 2024/1/1 -> 2024-1-1
    ]
    
    # Currency exchange rates (approximate, for normalization reference)
    EXCHANGE_RATES = {
        "USD": 1300,  # 1 USD = 1300 KRW (approximate)
        "EUR": 1400,
        "JPY": 9,     # 100 JPY = 900 KRW
    }

    def normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply all normalization steps to extracted data.
        
        Args:
            data: Raw extracted data
            
        Returns:
            Normalized data
        """
        normalized = data.copy()
        
        # Normalize title and summary
        if "title" in normalized:
            normalized["title"] = self._normalize_text(normalized["title"])
        if "summary" in normalized:
            normalized["summary"] = self._normalize_text(normalized["summary"])
        
        # Normalize tables
        if "tables" in normalized:
            normalized["tables"] = [
                self._normalize_table(table) for table in normalized["tables"]
            ]
        
        # Normalize key metrics
        if "key_metrics" in normalized:
            normalized["key_metrics"] = self._normalize_metrics(normalized["key_metrics"])
        
        # Add normalization metadata
        normalized["normalization"] = {
            "applied": True,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        return normalized
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text with term corrections and date standardization."""
        if not text:
            return text
        
        result = text
        
        # Apply term corrections
        for wrong, correct in self.TERM_CORRECTIONS.items():
            result = result.replace(wrong, correct)
        
        # Standardize dates
        result = self._standardize_dates(result)
        
        return result
    
    def _normalize_table(self, table: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single table."""
        normalized = table.copy()
        
        # Normalize headers
        if "headers" in normalized:
            normalized["headers"] = [
                self._normalize_text(str(h)) for h in normalized["headers"]
            ]
        
        # Normalize rows
        if "rows" in normalized:
            normalized["rows"] = [
                [self._normalize_cell(cell) for cell in row]
                for row in normalized["rows"]
            ]
        
        return normalized
    
    def _normalize_cell(self, cell: Any) -> Any:
        """Normalize a single cell value."""
        if cell is None:
            return ""
        
        cell_str = str(cell)
        
        # Apply text normalization
        cell_str = self._normalize_text(cell_str)
        
        # Try to parse as number
        cleaned = self._clean_number(cell_str)
        if cleaned is not None:
            return cleaned
        
        return cell_str
    
    def _normalize_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize key metrics."""
        normalized = {}
        
        for key, value in metrics.items():
            # Normalize key name
            norm_key = self._normalize_text(key)
            
            # Normalize value
            if isinstance(value, str):
                cleaned = self._clean_number(value)
                norm_value = cleaned if cleaned is not None else value
            else:
                norm_value = value
            
            normalized[norm_key] = norm_value
        
        return normalized
    
    def _standardize_dates(self, text: str) -> str:
        """Standardize date formats to ISO format."""
        result = text
        
        for pattern, replacement in self.DATE_PATTERNS:
            matches = re.findall(pattern, result)
            for match in matches:
                if isinstance(match, tuple):
                    year, month, day = match
                    # Zero-pad month and day
                    standardized = f"{year}-{int(month):02d}-{int(day):02d}"
                    original = re.search(pattern, result).group(0)
                    result = result.replace(original, standardized, 1)
        
        return result
    
    def _clean_number(self, value: str) -> Optional[float]:
        """Clean and parse a number string."""
        if not value or not isinstance(value, str):
            return None
        
        # Remove common formatting
        cleaned = value.strip()
        cleaned = cleaned.replace(",", "")
        cleaned = cleaned.replace(" ", "")
        
        # Remove currency symbols
        cleaned = re.sub(r'[$€¥₩]', '', cleaned)
        cleaned = re.sub(r'(USD|EUR|JPY)', '', cleaned)
        
        # Handle percentages
        is_percentage = "%" in cleaned
        cleaned = cleaned.replace("%", "")
        
        # Handle negative numbers
        is_negative = cleaned.startswith("-") or cleaned.startswith("(")
        cleaned = cleaned.replace("-", "").replace("(", "").replace(")", "")
        
        # Try to parse
        try:
            result = float(cleaned) * multiplier
            if is_negative:
                result = -result
            if is_percentage:
                result = result / 100
            return result
        except ValueError:
            return None
    
    def get_currency_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and standardize currency information."""
        currency = data.get("currency", "USD")
        
        return {
            "primary_currency": currency,
            "exchange_rate_to_usd": 1.0, # Base is USD in v11.5
            "detected_currencies": self._detect_currencies(str(data))
        }
    
    def _detect_currencies(self, text: str) -> List[str]:
        """Detect mentioned currencies in text."""
        currencies = []
        
        patterns = [
            (r'\$|USD', 'USD'),
            (r'€|EUR', 'EUR'),
            (r'¥|JPY', 'JPY'),
        ]
        
        for pattern, currency in patterns:
            if re.search(pattern, text):
                currencies.append(currency)
        
        return list(set(currencies))


# Singleton instance
normalizer = FinancialNormalizer()
