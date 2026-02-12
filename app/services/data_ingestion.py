import polars as pl
import aiohttp
import logging
import os
import time
import asyncio
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

_ticker_cache: Optional[Tuple[float, Dict[str, Dict[str, Any]]]] = None
_ticker_cache_lock = asyncio.Lock()
_ticker_cache_ttl_s = int(os.getenv("SEC_TICKER_CACHE_TTL_S", "3600") or "3600")


def _sec_user_agent() -> str:
    ua = (os.getenv("SEC_USER_AGENT") or "").strip()
    if ua:
        return ua
    return "Preciso/1.0 (contact: dev@preciso.local)"


async def _fetch_json(url: str) -> Dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": _sec_user_agent()}) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"SEC fetch failed {resp.status}: {text[:200]}")
            return await resp.json()


async def _resolve_cik_from_ticker(ticker: str) -> Optional[str]:
    if not ticker:
        return None
    if ticker.isdigit():
        return ticker.zfill(10)
    url = "https://www.sec.gov/files/company_tickers.json"
    async with _ticker_cache_lock:
        global _ticker_cache
        now = time.time()
        if _ticker_cache and (_ticker_cache[0] + _ticker_cache_ttl_s) > now:
            data = _ticker_cache[1]
        else:
            data = await _fetch_json(url)
            _ticker_cache = (now, data)
    t = ticker.upper()
    for _, item in data.items():
        if str(item.get("ticker", "")).upper() == t:
            cik = str(item.get("cik_str") or "").strip()
            if cik:
                return cik.zfill(10)
    return None

class DataIngestionService:
    async def fetch_sec_filings(self, ticker: str, limit: int = 10) -> pl.DataFrame:
        """
        Fetch recent SEC filings using data.sec.gov submissions endpoint.
        """
        logger.info("Fetching SEC filings for %s (limit=%s)", ticker, limit)
        try:
            cik = await _resolve_cik_from_ticker(ticker)
            if not cik:
                logger.warning("SEC ticker->CIK resolution failed for %s", ticker)
                return pl.DataFrame(
                    [
                        {
                            "filing_id": None,
                            "ticker": ticker,
                            "form": None,
                            "report_date": None,
                            "needs_review": True,
                            "error": "cik_resolution_failed",
                            "source": "sec",
                        }
                    ]
                )
            submissions = await _fetch_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
            recent = (submissions.get("filings") or {}).get("recent") or {}
            accessions = recent.get("accessionNumber") or []
            forms = recent.get("form") or []
            filing_dates = recent.get("filingDate") or []
        except (RuntimeError, ValueError, aiohttp.ClientError) as exc:
            logger.warning("SEC fetch failed for %s: %s", ticker, exc)
            return pl.DataFrame(
                [
                    {
                        "filing_id": None,
                        "ticker": ticker,
                        "form": None,
                        "report_date": None,
                        "needs_review": True,
                        "error": str(exc),
                        "source": "sec",
                    }
                ]
            )
        items = []
        for i, acc in enumerate(accessions[:limit]):
            items.append(
                {
                    "filing_id": str(acc),
                    "ticker": ticker,
                    "form": forms[i] if i < len(forms) else None,
                    "report_date": filing_dates[i] if i < len(filing_dates) else None,
                    "needs_review": False,
                    "error": None,
                    "source": "sec",
                }
            )
        return pl.DataFrame(items)

    async def fetch_fred_data(self, series_id: str, start_date: str, end_date: str) -> pl.DataFrame:
        """
        Fetch FRED series observations via market_data service.
        """
        logger.info("Fetching FRED data for %s (%s -> %s)", series_id, start_date, end_date)
        try:
            from app.services.market_data import market_data_service
        except (ImportError, RuntimeError, ValueError) as exc:
            return pl.DataFrame(
                [
                    {
                        "date": None,
                        "value": None,
                        "needs_review": True,
                        "error": str(exc),
                        "source": "fred",
                    }
                ]
            )

        # fetch a bounded number of observations (FRED API doesn't filter by date in this call)
        try:
            observations = await market_data_service.fetch_fred_series(series_id, limit=200)
        except (RuntimeError, ValueError, aiohttp.ClientError) as exc:
            return pl.DataFrame(
                [
                    {
                        "date": None,
                        "value": None,
                        "needs_review": True,
                        "error": str(exc),
                        "source": "fred",
                    }
                ]
            )
        if not observations:
            return pl.DataFrame(
                [
                    {
                        "date": None,
                        "value": None,
                        "needs_review": True,
                        "error": "no_observations",
                        "source": "fred",
                    }
                ]
            )
        rows = []
        for obs in observations:
            date = obs.get("date")
            if date and (date < start_date or date > end_date):
                continue
            rows.append(
                {
                    "date": date,
                    "value": obs.get("value"),
                    "needs_review": False,
                    "error": None,
                    "source": "fred",
                }
            )
        return pl.DataFrame(rows)
