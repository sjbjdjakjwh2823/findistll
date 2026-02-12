from __future__ import annotations

import asyncio
import logging
import os
from typing import List

from app.services.market_data import market_data_service
from app.services.market_ingest import ingest_snapshot
from app.services.metrics_logger import MetricsLogger
from app.api.v1.ingest import get_db

logger = logging.getLogger(__name__)


def _split_list(value: str) -> List[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


class MarketScheduler:
    def __init__(self) -> None:
        self.enabled = os.getenv("MARKET_SCHEDULE_ENABLED", "0") == "1"
        self.interval_s = int(os.getenv("MARKET_SCHEDULE_INTERVAL_S", "300"))
        self.symbols = _split_list(os.getenv("MARKET_SCHEDULE_SYMBOLS", ""))
        self.fred_series = _split_list(os.getenv("MARKET_SCHEDULE_FRED_SERIES", ""))
        self.fmp_symbols = _split_list(os.getenv("MARKET_SCHEDULE_FMP_SYMBOLS", ""))
        self.sec_symbols = _split_list(os.getenv("MARKET_SCHEDULE_SEC_SYMBOLS", ""))
        self.sec_forms = _split_list(os.getenv("MARKET_SCHEDULE_SEC_FORMS", "10-Q")) or ["10-Q"]

    async def _run_once(self) -> None:
        if not self.enabled:
            return
        db = get_db()
        for symbol in self.symbols:
            try:
                payload = await market_data_service.fetch_finnhub_quote(symbol, db=db)
                if payload.get("error"):
                    raise RuntimeError(payload.get("error"))
                normalized = market_data_service.normalize_market_snapshot(payload, "finnhub_quote", symbol=symbol)
                ingest_snapshot("finnhub_quote", symbol, normalized)
            except Exception as exc:
                MetricsLogger().log("market.fetch.failure", 1, {"source": "finnhub_quote"})
                logger.warning("market schedule failed for quote %s: %s", symbol, exc)
        for series_id in self.fred_series:
            try:
                observations = await market_data_service.fetch_fred_series(series_id, limit=5, db=db)
                if not observations:
                    raise RuntimeError("fred_series_empty")
                payload = [{**obs, "series_id": series_id} for obs in observations]
                normalized = market_data_service.normalize_market_snapshot(payload, "fred_series", symbol=series_id)
                ingest_snapshot("fred_series", series_id, normalized)
            except Exception as exc:
                MetricsLogger().log("market.fetch.failure", 1, {"source": "fred_series"})
                logger.warning("market schedule failed for FRED %s: %s", series_id, exc)
        for symbol in self.fmp_symbols:
            try:
                payload = await market_data_service.fetch_fmp_financial_statement_growth(symbol, db=db)
                if not payload:
                    raise RuntimeError("fmp_empty")
                normalized = market_data_service.normalize_market_snapshot(payload, "fmp_financial_statement_growth", symbol=symbol)
                ingest_snapshot("fmp_financial_statement_growth", symbol, normalized)
            except Exception as exc:
                MetricsLogger().log("market.fetch.failure", 1, {"source": "fmp_financial_statement_growth"})
                logger.warning("market schedule failed for FMP %s: %s", symbol, exc)
        for symbol in self.sec_symbols:
            for form in self.sec_forms:
                try:
                    payload = await market_data_service.fetch_sec_filings(symbol, form_type=form, limit=5, db=db)
                    if not payload:
                        raise RuntimeError("sec_empty")
                    normalized = market_data_service.normalize_market_snapshot(payload, "sec_filings", symbol=symbol)
                    ingest_snapshot("sec_filings", symbol, normalized)
                except Exception as exc:
                    MetricsLogger().log("market.fetch.failure", 1, {"source": "sec_filings"})
                    logger.warning("market schedule failed for SEC %s %s: %s", symbol, form, exc)

    async def run(self) -> None:
        if not self.enabled:
            logger.info("MarketScheduler disabled")
            return
        logger.info("MarketScheduler started interval=%ss", self.interval_s)
        while True:
            try:
                await self._run_once()
            except Exception:
                logger.exception("MarketScheduler loop error")
            await asyncio.sleep(self.interval_s)
