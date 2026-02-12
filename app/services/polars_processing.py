from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def process_with_polars(content: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Pure service module version of DataForge's Polars processing.

    Rationale:
    - `app.api.v1.ingest` imports FastAPI `File(...)` and triggers a hard runtime
      dependency on `python-multipart` at import time.
    - The conversion engine should not depend on API-layer imports.
    """
    try:
        import polars as pl  # noqa: F401
    except Exception:
        logger.warning("Polars not installed, using fallback processing")
        return content

    processed = dict(content)

    if source == "fred":
        return _process_fred_data(processed)
    if source in ("sec_10k", "sec_8k"):
        return _process_sec_data(processed)
    if source == "finnhub":
        return _process_finnhub_data(processed)
    if source == "fmp":
        return _process_fmp_data(processed)

    return processed


def _process_fred_data(content: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import polars as pl

        observations = content.get("observations", [])
        if not observations:
            return content
        df = pl.DataFrame(observations)
        if "value" in df.columns:
            df = df.with_columns(
                [
                    pl.col("value").cast(pl.Float64, strict=False).alias("value_numeric"),
                    pl.col("date").str.to_datetime("%Y-%m-%d", strict=False).alias("date_parsed"),
                ]
            )
            content["_polars_stats"] = {
                "mean": df["value_numeric"].mean(),
                "std": df["value_numeric"].std(),
                "min": df["value_numeric"].min(),
                "max": df["value_numeric"].max(),
                "count": len(df),
                "latest_date": str(df["date"].max()) if "date" in df.columns else None,
                "latest_value": df["value_numeric"].tail(1).to_list()[0] if len(df) > 0 else None,
            }
            content["_polars_processed"] = True
        return content
    except Exception as e:
        logger.warning("FRED Polars processing failed: %s", e)
        return content


def _process_sec_data(content: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import polars as pl

        facts = (content.get("facts") or {}).get("us-gaap", {})
        if not facts:
            return content
        metrics_data = []
        for concept, data in facts.items():
            units = data.get("units", {})
            for unit_type, values in units.items():
                for entry in values:
                    metrics_data.append(
                        {
                            "concept": concept,
                            "unit": unit_type,
                            "value": entry.get("val"),
                            "period_end": entry.get("end"),
                            "period_start": entry.get("start"),
                            "form": entry.get("form"),
                            "fiscal_year": entry.get("fy"),
                            "fiscal_period": entry.get("fp"),
                        }
                    )
        if metrics_data:
            df = pl.DataFrame(metrics_data)
            summary = df.group_by("concept").agg(
                [
                    pl.col("value").last().alias("latest_value"),
                    pl.col("period_end").max().alias("latest_period"),
                    pl.count().alias("observation_count"),
                ]
            )
            content["_polars_metrics_summary"] = summary.to_dicts()
            content["_polars_processed"] = True
            content["_polars_total_metrics"] = len(metrics_data)
        return content
    except Exception as e:
        logger.warning("SEC Polars processing failed: %s", e)
        return content


def _process_finnhub_data(content: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import polars as pl

        if "c" in content and "t" in content:
            df = pl.DataFrame(
                {
                    "close": content.get("c", []),
                    "high": content.get("h", []),
                    "low": content.get("l", []),
                    "open": content.get("o", []),
                    "volume": content.get("v", []),
                    "timestamp": content.get("t", []),
                }
            )
            if len(df) > 0:
                content["_polars_stats"] = {
                    "avg_close": df["close"].mean(),
                    "avg_volume": df["volume"].mean(),
                    "price_range": df["high"].max() - df["low"].min(),
                    "data_points": len(df),
                }
                content["_polars_processed"] = True
        return content
    except Exception as e:
        logger.warning("Finnhub Polars processing failed: %s", e)
        return content


def _process_fmp_data(content: Any) -> Dict[str, Any]:
    try:
        import polars as pl

        if isinstance(content, list) and len(content) > 0:
            df = pl.DataFrame(content)
            return {
                "data": content,
                "_polars_columns": df.columns,
                "_polars_row_count": len(df),
                "_polars_processed": True,
            }
        if isinstance(content, dict):
            return content
        return {"content": content, "_polars_processed": False}
    except Exception as e:
        logger.warning("FMP Polars processing failed: %s", e)
        if isinstance(content, dict):
            return content
        return {"content": content}

