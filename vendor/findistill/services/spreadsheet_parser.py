import polars as pl
import pandas as pd
import re
import logging
import os
from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import datetime
from .xbrl_semantic_engine import SemanticFact, UnitManager, ScaleProcessor

logger = logging.getLogger(__name__)

class SpreadsheetParser:
    """
    Parses quantitative data from Excel/CSV files using Polars.
    Identifies financial time-series structure using heuristic header analysis.
    v17.0: Migrated to Polars for performance.
    """
    
    def __init__(self, file_content: bytes, file_type: str = 'xlsx'):
        self.content = file_content
        self.file_type = file_type
        
    def parse(self) -> List[SemanticFact]:
        """Main parsing logic."""
        import io
        
        try:
            if self.file_type == 'csv':
                try:
                    df = pl.read_csv(io.BytesIO(self.content))
                except Exception as e:
                    logger.warning(f"Polars read_csv failed, falling back to pandas: {e}")
                    pd_df = pd.read_csv(io.BytesIO(self.content))
                    df = pl.from_pandas(pd_df)
            else:
                # Polars read_excel requires fastexcel or xlsx2csv
                # We assume these are installed as per requirements.
                try:
                    df = pl.read_excel(io.BytesIO(self.content))
                except Exception as e:
                    logger.warning(f"Polars read_excel failed, falling back to pandas: {e}")
                    try:
                        pd_df = pd.read_excel(io.BytesIO(self.content), engine="openpyxl")
                        df = pl.from_pandas(pd_df)
                    except Exception as e2:
                        logger.error(f"Pandas read_excel failed: {e2}")
                        raise ValueError(f"Failed to parse Excel file: {e2}")
            
            if os.getenv("PRECISO_DEBUG_LOGS", "0") == "1":
                logger.info("SpreadsheetParser: Loaded DataFrame shape=%s columns=%s", df.shape, df.columns)
            
            return self._process_dataframe(df)
            
        except Exception as e:
            logger.error(f"Spreadsheet Parsing Error: {e}")
            raise

    def _process_dataframe(self, df: pl.DataFrame) -> List[SemanticFact]:
        facts = []
        
        # 0. Global Scale Detection (Header Analysis)
        scale_multiplier = Decimal(1)
        scale_context = "raw"
        
        preview_str = str(df.head(5)).lower()
        
        if "million" in preview_str:
            scale_multiplier = Decimal("1000000")
            scale_context = "millions"
        elif "thousand" in preview_str:
            scale_multiplier = Decimal("1000")
            scale_context = "thousands"
        elif "billion" in preview_str:
            scale_multiplier = Decimal("1000000000")
            scale_context = "billions"
        else:
            try:
                num_col = None
                for c in df.columns:
                    if df[c].dtype.is_numeric():
                        num_col = c
                        break

                if num_col:
                    max_val = df[num_col].max()
                    if max_val and 1000 < max_val < 500000:
                        logger.warning("No unit text found. Inferring 'Millions' scale based on value magnitude.")
                        scale_multiplier = Decimal("1000000")
                        scale_context = "inferred_millions"
            except Exception:
                logger.debug("Scale detection fallback failed", exc_info=True)
            
        logger.info(f"SpreadsheetParser: Detected global scale: {scale_context} (x{scale_multiplier})")

        # 1. Identify Header Row (Smart Scan)
        header_row_idx = 0
        year_cols = {} # col_name -> normalized_period (e.g. "CY", "PY")
        
        def find_years(row_values):
            found = []
            for val in row_values:
                # Avoid false positives like 20403.0 -> "2040" (year) by:
                # - Accepting numeric years only when the cell itself is a plausible year
                # - Accepting string matches for year patterns
                if isinstance(val, (int,)):
                    if 1990 <= val <= 2035:
                        found.append(int(val))
                    continue
                if isinstance(val, (float,)):
                    if val.is_integer() and 1990 <= int(val) <= 2035:
                        found.append(int(val))
                    continue

                s = str(val).strip()
                m = re.search(r"(20\d{2})", s)
                if m:
                    try:
                        y = int(m.group(1))
                        if 1990 <= y <= 2035:
                            found.append(y)
                    except Exception:
                        logger.debug("year parse failed for %s", s, exc_info=True)
                    continue

                m2 = re.search(r"(?:CY|FY|')(\d{2})", s, re.IGNORECASE)
                if m2:
                    try:
                        y = 2000 + int(m2.group(1))
                        if 1990 <= y <= 2035:
                            found.append(y)
                    except Exception:
                        logger.debug("year short parse failed for %s", s, exc_info=True)
            return found

        logger.info(f"SpreadsheetParser: Initial columns: {df.columns}")
        years = find_years(df.columns)
        logger.info(f"SpreadsheetParser: Initial years found: {years}")
        best_year_count = len(years)
        best_header_row = -1
        
        # Scan first 10 rows for better headers
        for i in range(min(10, len(df))):
            row_vals = df.row(i) # Returns tuple
            row_years = find_years(row_vals)
            if os.getenv("PRECISO_DEBUG_LOGS", "0") == "1":
                logger.info("SpreadsheetParser: Row %s scan: %s -> Found years: %s", i, row_vals, row_years)
            if len(row_years) > best_year_count:
                best_year_count = len(row_years)
                best_header_row = i
                
        if best_header_row != -1:
            # Polars doesn't support easy "promote row to header" like pandas
            # We must reload or rename. Renaming is easier if we just treat current row as header.
            # But values are typed. Header row might be strings in a mixed column?
            # Safer to rename columns based on the row values
            new_header = [str(v) for v in df.row(best_header_row)]
            
            # Rename columns
            mapping = {old: new for old, new in zip(df.columns, new_header)}
            df = df.rename(mapping)
            
            # Slice off the header rows
            df = df.slice(best_header_row + 1)
            
            logger.info(f"SpreadsheetParser: Found better header at row {best_header_row}: {new_header}")
            
        years_found = []
        for col in df.columns:
            col_str = str(col)
            match = re.search(r'(20\d{2})', col_str)
            if match:
                years_found.append(int(match.group(1)))
            else:
                m2 = re.search(r'(?:CY|FY|\')(\d{2})', col_str, re.IGNORECASE)
                if m2:
                    years_found.append(2000 + int(m2.group(1)))
                
        if not years_found:
            logger.warning(f"No year columns found in spreadsheet after smart scan. Columns: {df.columns}")
            return []
            
        cy_year = max(years_found)
        logger.info(f"SpreadsheetParser: CY Year determined: {cy_year}")
        
        for col in df.columns:
            col_str = str(col)
            y = None
            match = re.search(r'(20\d{2})', col_str)
            if match:
                y = int(match.group(1))
            else:
                m2 = re.search(r'(?:CY|FY|\')(\d{2})', col_str, re.IGNORECASE)
                if m2:
                    y = 2000 + int(m2.group(1))
            
            if y:
                if y == cy_year:
                    year_cols[col] = "CY"
                else:
                    year_cols[col] = f"PY_{y}"
        
        logger.info(f"SpreadsheetParser: Mapped years: {year_cols}")

        label_col = None
        for col in df.columns:
            if col in year_cols: continue
            label_col = col
            break
        
        if not label_col:
            label_col = df.columns[0]
            
        logger.info(f"SpreadsheetParser: Using label column: {label_col}")

        # 3. Extract Facts
        # iter_rows(named=True) yields dict-like rows
        for row in df.iter_rows(named=True):
            label_raw = str(row[label_col])
            
            if not label_raw or label_raw.lower() == 'nan' or label_raw.lower() == 'null':
                continue
                
            concept = re.sub(r'[^a-zA-Z0-9]', '', label_raw)
            
            for col, period in year_cols.items():
                raw_val = row[col]
                
                try:
                    val_str = str(raw_val).replace(',', '').replace('$', '').replace(')', '').replace('(', '-')
                    
                    if not val_str or val_str.lower() == 'nan' or val_str.lower() == 'null' or val_str.strip() == '-':
                        continue
                        
                    val_decimal = Decimal(val_str)
                    
                    is_per_share = 'share' in label_raw.lower() or 'eps' in label_raw.lower()
                    
                    if not is_per_share:
                        val_decimal *= scale_multiplier
                    
                    unit_type = 'currency'
                    if 'share' in label_raw.lower():
                        unit_type = 'shares'
                    elif 'eps' in label_raw.lower() or 'earnings per share' in label_raw.lower():
                        unit_type = 'ratio' 
                    elif 'margin' in label_raw.lower() or 'percent' in label_raw.lower():
                        unit_type = 'ratio'
                    elif 'ratio' in label_raw.lower() and 'operation' not in label_raw.lower():
                         unit_type = 'ratio'
                    
                    final_val, tag, conf_score = ScaleProcessor.apply_self_healing(str(val_decimal), None, unit_type)
                    
                    fact = SemanticFact(
                        concept=concept,
                        label=label_raw,
                        value=final_val,
                        raw_value=str(raw_val),
                        unit=unit_type,
                        period=period,
                        context_ref=f"ctx_{period}",
                        decimals=None,
                        is_consolidated=True,
                        confidence_score=conf_score
                    )
                    if tag != "raw_pass":
                        fact.tags.append(tag)
                        
                    facts.append(fact)
                    
                except Exception:
                    continue
                    
        return facts

    def get_metadata(self) -> Dict[str, str]:
        return {"company": "Unknown Spreadsheet", "year": "2024"}
