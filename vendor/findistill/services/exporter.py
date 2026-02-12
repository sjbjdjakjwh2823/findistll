"""
FinDistill Multi-Format Exporter

Exports normalized financial data to:
- JSONL: For LLM fine-tuning
- Markdown: For RAG systems
- Parquet: For analytics (columnar storage)
- HDF5: For large-scale numerical/time-series data
"""

import json
import logging
import os
from typing import Dict, Any
from datetime import datetime

# Avoid configuring global logging in a library module. The application should configure logging.
if os.getenv("PRECISO_CONFIGURE_LOGGING", "0") == "1":
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataExporter:
    """Exports financial data to various formats for AI training."""

    def export_facts(self, facts, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize SemanticFact list into a stable table structure.
        This avoids hard failures when only facts are available.
        """
        def _get(item, key):
            if isinstance(item, dict):
                return item.get(key)
            return getattr(item, key, None)
        rows = []
        for fact in facts or []:
            row = {
                "concept": _get(fact, "concept"),
                "value": _get(fact, "value"),
                "raw_value": _get(fact, "raw_value"),
                "normalized_value": _get(fact, "normalized_value"),
                "period": _get(fact, "period"),
                "unit": _get(fact, "unit"),
                "currency": _get(fact, "currency"),
                "entity": _get(fact, "entity"),
                "dimensions": _get(fact, "dimensions"),
                "source": _get(fact, "source"),
                "confidence": _get(fact, "confidence"),
                "evidence": _get(fact, "evidence"),
            }
            rows.append(row)

        return {
            "title": metadata.get("company", "Financial Document"),
            "metadata": metadata or {},
            "tables": [
                {
                    "name": "facts",
                    "headers": [
                        "concept",
                        "value",
                        "raw_value",
                        "normalized_value",
                        "period",
                        "unit",
                        "currency",
                        "entity",
                        "dimensions",
                        "source",
                        "confidence",
                        "evidence",
                    ],
                    "rows": [
                        [r.get(h) for h in [
                            "concept",
                            "value",
                            "raw_value",
                            "normalized_value",
                            "period",
                            "unit",
                            "currency",
                            "entity",
                            "dimensions",
                            "source",
                            "confidence",
                            "evidence",
                        ]]
                        for r in rows
                    ],
                }
            ],
        }
    
    def to_jsonl(self, data: Dict[str, Any]) -> str:
        """
        Convert to JSONL format exclusively using reasoning_qa.
        Surgical removal: legacy short-form logic (Row 2+) removed.
        """
        # Note: reasoning_qa already contains summary and trend pairs in 4-step CoT format.
        reasoning_qa = data.get("reasoning_qa", [])
        
        # If the backend engine provided JSONL data directly (with Poison Pill already applied), reuse it.
        # This occurs in the v11.5 strict pipeline.
        if "jsonl_data" in data and data["jsonl_data"]:
            return "\n".join(data["jsonl_data"])
            
        if not reasoning_qa:
            # Keep exports robust: some ingestion paths produce facts without CoT/Q&A.
            # For AI training, quant, and RAG, it's better to emit a minimal JSONL than fail the whole pipeline.
            facts = data.get("facts", []) or []
            if not facts:
                logger.warning("reasoning_qa is empty and no facts were extracted. Returning empty JSONL.")
                return ""

            def chunks(items, n):
                for i in range(0, len(items), n):
                    yield items[i:i+n]

            lines = []
            for chunk in chunks(facts, 50):
                entry = {
                    "instruction": "Normalize extracted financial facts into structured JSON for downstream analysis.",
                    "input": data.get("title", "Financial Document"),
                    "output": json.dumps({"facts": chunk}, ensure_ascii=False),
                    "metadata": data.get("metadata", {}),
                }
                lines.append(json.dumps(entry, ensure_ascii=False))
            return "\n".join(lines)

        # Fallback for data structures without pre-generated JSONL
        lines = []
        for qa in reasoning_qa:
            entry = {
                "instruction": qa.get("question", "Analyze the financial data."),
                "input": data.get("title", "Financial Document"),
                "output": qa.get("response", ""),
                "metadata": data.get("metadata", {})
            }
            lines.append(json.dumps(entry, ensure_ascii=False))
            
        # Final check: Double validation
        if not lines:
             raise ValueError("CRITICAL ERROR: JSONL line generation failed despite presence of reasoning_qa.")

        if os.getenv("PRECISO_DEBUG_LOGS", "0") == "1":
            logger.info("EXPORT READY: %s rows", len(lines))
        
        return "\n".join(lines)
    
    def to_markdown(self, data: Dict[str, Any]) -> str:
        """Convert to Markdown format for RAG systems."""
        md_lines = []
        
        # Title
        title = data.get("title", "Financial Document")
        md_lines.append(f"# {title}")
        md_lines.append("")
        
        # Metadata
        if "metadata" in data:
            md_lines.append("## Document Information")
            for key, value in data["metadata"].items():
                md_lines.append(f"- **{key}**: {value}")
            md_lines.append("")
        
        # Summary
        if "summary" in data:
            md_lines.append("## Summary")
            md_lines.append(data["summary"])
            md_lines.append("")
        
        # Key Metrics
        if "key_metrics" in data and data["key_metrics"]:
            md_lines.append("## Key Metrics")
            md_lines.append("")
            md_lines.append("| Metric | Value |")
            md_lines.append("|------|-----|")
            for metric, value in data["key_metrics"].items():
                md_lines.append(f"| {metric} | {value} |")
            md_lines.append("")
        
        # Tables
        for i, table in enumerate(data.get("tables", []), 1):
            table_name = table.get("name", f"Table {i}")
            headers = table.get("headers", [])
            rows = table.get("rows", [])
            
            md_lines.append(f"## {table_name}")
            md_lines.append("")
            
            if headers:
                # Sanitized headers
                safe_headers = [str(h).replace("|", "\\|") for h in headers]
                md_lines.append("| " + " | ".join(safe_headers) + " |")
                md_lines.append("|" + "|".join(["---"] * len(headers)) + "|")
                
                for row in rows:
                    padded_row = list(row) + [""] * (len(headers) - len(row))
                    safe_row = [str(v).replace("|", "\\|") for v in padded_row[:len(headers)]]
                    md_lines.append("| " + " | ".join(safe_row) + " |")
            
            md_lines.append("")
        
        # Footer
        md_lines.append("---")
        md_lines.append(f"*Generated by FinDistill at {datetime.now().isoformat()}*")
        
        return "\n".join(md_lines)
    
    def to_parquet(self, data: Dict[str, Any]) -> bytes:
        """
        Convert to Parquet format using Polars.
        Warning: This requires polars/fastexcel which are not installed in serverless mode to save size.
        Will raise an error if called.
        """
        try:
            import polars as pl
            import io
            
            # Implementation if libraries exist
            dfs = []
            for table in data.get("tables", []):
                table_name = table.get("name", "Unknown")
                headers = table.get("headers", [])
                rows = table.get("rows", [])
                
                if headers and rows:
                    # Clean rows to ensure string consistency or let polars infer?
                    # Polars orient='row' expects keys if using list of dicts, or just list of lists if schema is provided.
                    # Warning: rows must be list of lists.
                    try:
                        # Some tables contain mixed numeric/text cells (footnotes, labels).
                        # For export robustness, coerce cells to strings here; typed analytics should
                        # use Spoke B facts/features Parquet instead of raw mixed tables.
                        cleaned_rows = [
                            [None if v is None else str(v) for v in row]
                            for row in rows
                        ]
                        df = pl.DataFrame(cleaned_rows, schema=headers, orient="row")
                        df = df.with_columns(pl.lit(table_name).alias("_source_table"))
                        dfs.append(df)
                    except Exception as e:
                        logger.warning(f"Skipping table {table_name} due to Polars creation error: {e}")
            
            if not dfs:
                 combined = pl.DataFrame({"info": ["no data"]})
            else:
                 combined = pl.concat(dfs, how="diagonal")
            
            buffer = io.BytesIO()
            combined.write_parquet(buffer, compression='snappy')
            return buffer.getvalue()
            
        except ImportError:
            raise RuntimeError("Parquet export not supported in serverless mode (requires polars)")

    def to_triples_csv(self, triples: list) -> str:
        """
        Convert Spoke D triples into CSV format:
        head_node,relation,tail_node,properties
        """
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["head_node", "relation", "tail_node", "properties"])
        for t in triples or []:
            writer.writerow([
                t.get("head_node"),
                t.get("relation"),
                t.get("tail_node"),
                json.dumps(t.get("properties"), ensure_ascii=False),
            ])
        return output.getvalue()

    def to_hdf5(self, data: Dict[str, Any]) -> bytes:
        """
        Convert to HDF5 format for large-scale numerical and time-series data.
        Uses float64 precision for financial data accuracy.
        
        Warning: Requires h5py and numpy.
        """
        try:
            import h5py
            import numpy as np
            import io
            
            buffer = io.BytesIO()
            
            with h5py.File(buffer, 'w') as f:
                # Store metadata as attributes
                meta_group = f.create_group("metadata")
                meta_group.attrs["title"] = data.get("title", "Financial Document")
                meta_group.attrs["summary"] = data.get("summary", "")
                meta_group.attrs["created_at"] = datetime.now().isoformat()
                
                # Store key metrics
                if "key_metrics" in data and data["key_metrics"]:
                    metrics_group = f.create_group("key_metrics")
                    for key, value in data["key_metrics"].items():
                        # Try to convert to float64 for precision
                        try:
                            numeric_value = float(str(value).replace(",", "").replace("%", ""))
                            metrics_group.create_dataset(
                                key, 
                                data=np.array([numeric_value], dtype=np.float64)
                            )
                        except (ValueError, TypeError):
                            # Store as string if not numeric
                            metrics_group.attrs[key] = str(value)
                
                # Store tables
                tables_group = f.create_group("tables")
                for i, table in enumerate(data.get("tables", [])):
                    table_name = table.get("name", f"table_{i}")
                    # Clean table name for HDF5 compatibility
                    safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in table_name)
                    
                    table_group = tables_group.create_group(safe_name)
                    headers = table.get("headers", [])
                    rows = table.get("rows", [])
                    
                    # Store headers
                    if headers:
                        table_group.attrs["headers"] = json.dumps(headers, ensure_ascii=False)
                    
                    # Try to store as numeric array with float64 precision
                    if rows:
                        try:
                            # Attempt to convert to numeric (for financial data)
                            numeric_rows = []
                            for row in rows:
                                numeric_row = []
                                for val in row:
                                    try:
                                        # Clean and convert to float64
                                        clean_val = str(val).replace(",", "").replace("%", "").replace("$", "").replace("₩", "")
                                        numeric_row.append(float(clean_val))
                                    except (ValueError, TypeError):
                                        numeric_row.append(float('nan'))
                                numeric_rows.append(numeric_row)
                            
                            # Store as float64 array for precision
                            table_group.create_dataset(
                                "data",
                                data=np.array(numeric_rows, dtype=np.float64),
                                compression="gzip"
                            )
                        except Exception:
                            # Fallback: store as JSON string
                            table_group.attrs["data_json"] = json.dumps(rows, ensure_ascii=False)
            
            return buffer.getvalue()
            
        except ImportError:
            raise RuntimeError("HDF5 export not supported (requires h5py/numpy). Install with: pip install h5py numpy")

    def to_kg_triples(self, data: Dict[str, Any]) -> list:
        """Convert facts to Knowledge Graph triples."""
        triples = []
        for fact in data.get("facts", []) or []:
            concept = fact.get("concept") or fact.get("label")
            value = fact.get("value")
            period = fact.get("period")
            unit = fact.get("unit")
            if concept is None or value is None:
                continue
            triples.append({"subject": concept, "predicate": "value", "object": value})
            if period:
                triples.append({"subject": concept, "predicate": "period", "object": period})
            if unit:
                triples.append({"subject": concept, "predicate": "unit", "object": unit})
        return triples

    def _table_to_text(self, table: Dict[str, Any]) -> str:
        """Convert a table to readable text format."""
        lines = []
        headers = table.get("headers", [])
        rows = table.get("rows", [])
        
        if headers:
            lines.append("Columns: " + ", ".join(str(h) for h in headers))
        
        for i, row in enumerate(rows[:5], 1):
            val_strs = [str(v) for v in row]
            lines.append(f"Row {i}: " + ", ".join(val_strs))
        
        if len(rows) > 5:
            lines.append(f"... and {len(rows) - 5} other rows")
        
        return "\n".join(lines)


# Singleton instance
exporter = DataExporter()
