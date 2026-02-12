import os
import aiohttp
import logging
import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

class MarketDataService:
    """Service to fetch real-time market and policy data (FRED, Finnhub, etc.)."""
    
    def __init__(self):
        self.base_url_fred = "https://api.stlouisfed.org/fred"
        self.base_url_fmp = "https://financialmodelingprep.com/api/v3"
        self.base_url_sec = "https://api.sec-api.io"
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl_s = int(os.getenv("MARKET_FETCH_CACHE_TTL_S", "30") or "30")
        self._net_sema = asyncio.Semaphore(int(os.getenv("MARKET_FETCH_CONCURRENCY", "8") or "8"))
        self._timeout_s = int(os.getenv("MARKET_FETCH_TIMEOUT_S", "20") or "20")
        self._session: Optional[aiohttp.ClientSession] = None

    async def close(self) -> None:
        sess = self._session
        self._session = None
        if sess and not sess.closed:
            await sess.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session
        timeout = aiohttp.ClientTimeout(total=self._timeout_s)
        # Reuse one session to reduce connection setup overhead.
        self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def _resolve_key(self, provider: str, api_key_override: Optional[str], db: Optional[Any]) -> Optional[str]:
        if api_key_override:
            return api_key_override
        try:
            from app.services.integration_keys import resolve_integration_key
            return resolve_integration_key(db=db, provider=provider)
        except Exception:
            # Fall back to env-only.
            return None

    @property
    def fred_api_key(self):
        return os.getenv("FRED_API_KEY")

    @property
    def finnhub_api_key(self):
        return os.getenv("FINNHUB_API_KEY")

    @property
    def fmp_api_key(self):
        return os.getenv("FMP_API_KEY")

    @property
    def sec_api_key(self):
        return os.getenv("SEC_API_KEY")

    async def _fetch_json(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # Cache key: url + sorted params
        try:
            key = url + "?" + "&".join([f"{k}={params[k]}" for k in sorted(params.keys())])
        except Exception:
            key = url

        now = time.time()
        cached = self._cache.get(key)
        if cached and cached.get("expires_at", 0) > now:
            return cached.get("value") or {}

        retries = int(os.getenv("MARKET_FETCH_RETRIES", "2") or "2")
        backoff = float(os.getenv("MARKET_FETCH_BACKOFF_S", "0.6") or "0.6")

        async with self._net_sema:
            for attempt in range(retries + 1):
                try:
                    session = await self._get_session()
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            # Some providers mislabel content-type; allow parsing anyway.
                            data = await response.json(content_type=None)
                            self._cache[key] = {"expires_at": time.time() + self._cache_ttl_s, "value": data}
                            return data

                        # Retry on rate-limit and transient server errors
                        if response.status in (429, 500, 502, 503, 504) and attempt < retries:
                            await asyncio.sleep(backoff * (2 ** attempt))
                            continue

                        error_text = await response.text()
                        logger.error(f"Market API error ({response.status}): {error_text}")
                        return {"error": error_text, "status": response.status}
                except Exception as e:
                    if attempt < retries:
                        await asyncio.sleep(backoff * (2 ** attempt))
                        continue
                    return {"error": str(e), "status": 599}

    async def _post_json(self, url: str, json_body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        retries = int(os.getenv("MARKET_FETCH_RETRIES", "2") or "2")
        backoff = float(os.getenv("MARKET_FETCH_BACKOFF_S", "0.6") or "0.6")
        hdrs = headers or {"Content-Type": "application/json"}
        async with self._net_sema:
            for attempt in range(retries + 1):
                try:
                    session = await self._get_session()
                    async with session.post(url, json=json_body, headers=hdrs) as response:
                        if response.status == 200:
                            return await response.json(content_type=None)
                        if response.status in (429, 500, 502, 503, 504) and attempt < retries:
                            await asyncio.sleep(backoff * (2 ** attempt))
                            continue
                        error_text = await response.text()
                        return {"error": error_text, "status": response.status}
                except Exception as e:
                    if attempt < retries:
                        await asyncio.sleep(backoff * (2 ** attempt))
                        continue
                    return {"error": str(e), "status": 599}

    async def fetch_fred_series(
        self,
        series_id: str,
        limit: int = 1,
        *,
        observation_start: Optional[str] = None,
        observation_end: Optional[str] = None,
        api_key_override: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch observations for a specific FRED series ID."""
        api_key = self._resolve_key("fred", api_key_override, db) or self.fred_api_key
        if not api_key:
            logger.error("FRED_API_KEY not found in environment.")
            return []

        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit
        }
        if observation_start:
            params["observation_start"] = observation_start
        if observation_end:
            params["observation_end"] = observation_end

        url = f"{self.base_url_fred}/series/observations"
        data = await self._fetch_json(url, params)
        return data.get("observations", []) if isinstance(data, dict) else []

    async def get_key_rates(
        self,
        *,
        api_key_override: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Fetch key interest rates and policy data."""
        # FEDFUNDS: Federal Funds Effective Rate
        # GS10: 10-Year Treasury Constant Maturity Rate
        # T10Y2Y: 10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity
        
        series_ids = {
            "fed_funds": "FEDFUNDS",
            "treasury_10y": "GS10",
            "yield_curve": "T10Y2Y"
        }
        
        results = {}
        for label, sid in series_ids.items():
            obs = await self.fetch_fred_series(sid, api_key_override=api_key_override, db=db)
            if obs:
                results[label] = {
                    "value": obs[0]["value"],
                    "date": obs[0]["date"],
                    "series_id": sid
                }
        
        return results

    async def fetch_finnhub_quote(
        self,
        symbol: str,
        *,
        api_key_override: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Fetch real-time quote for a symbol (stocks, FX, crypto)."""
        api_key = self._resolve_key("finnhub", api_key_override, db) or self.finnhub_api_key
        if not api_key:
            logger.error("FINNHUB_API_KEY not found in environment.")
            return {"error": "missing_finnhub_api_key"}
        url = "https://finnhub.io/api/v1/quote"
        params = {"symbol": symbol, "token": api_key}
        return await self._fetch_json(url, params)

    async def fetch_finnhub_news(
        self,
        category: str = "general",
        symbol: Optional[str] = None,
        *,
        api_key_override: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch news by category or company symbol."""
        api_key = self._resolve_key("finnhub", api_key_override, db) or self.finnhub_api_key
        if not api_key:
            logger.error("FINNHUB_API_KEY not found in environment.")
            return []
        if symbol:
            url = "https://finnhub.io/api/v1/company-news"
            today = datetime.now(timezone.utc).date().isoformat()
            params = {"symbol": symbol, "from": today, "to": today, "token": api_key}
        else:
            url = "https://finnhub.io/api/v1/news"
            params = {"category": category, "token": api_key}
        data = await self._fetch_json(url, params)
        return data if isinstance(data, list) else []

    async def fetch_finnhub_forex(
        self,
        base: str,
        quote: str,
        *,
        api_key_override: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Fetch FX rates (base -> quote)."""
        api_key = self._resolve_key("finnhub", api_key_override, db) or self.finnhub_api_key
        if not api_key:
            logger.error("FINNHUB_API_KEY not found in environment.")
            return {"error": "missing_finnhub_api_key"}
        url = "https://finnhub.io/api/v1/forex/rates"
        params = {"base": base, "token": api_key}
        data = await self._fetch_json(url, params)
        return data if isinstance(data, dict) else {}

    async def fetch_finnhub_crypto(
        self,
        symbol: str,
        *,
        api_key_override: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Fetch crypto price by symbol (e.g., BINANCE:BTCUSDT)."""
        api_key = self._resolve_key("finnhub", api_key_override, db) or self.finnhub_api_key
        if not api_key:
            logger.error("FINNHUB_API_KEY not found in environment.")
            return {"error": "missing_finnhub_api_key"}
        url = "https://finnhub.io/api/v1/crypto/price"
        params = {"symbol": symbol, "token": api_key}
        return await self._fetch_json(url, params)

    async def fetch_fmp_financial_statement_growth(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
        *,
        api_key_override: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch financial statement growth for a given symbol."""
        api_key = self._resolve_key("fmp", api_key_override, db) or self.fmp_api_key
        if not api_key:
            logger.error("FMP_API_KEY not found in environment.")
            return []
        url = f"{self.base_url_fmp}/income-statement-growth/{symbol}"
        params = {"period": period, "limit": limit, "apikey": api_key}
        data = await self._fetch_json(url, params)
        return data if isinstance(data, list) else []

    async def fetch_sec_filings(
        self,
        symbol: str,
        form_type: str = "10-K",
        limit: int = 1,
        *,
        api_key_override: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch SEC filings for a given symbol and form type."""
        api_key = self._resolve_key("sec", api_key_override, db) or self.sec_api_key
        if not api_key:
            logger.error("SEC_API_KEY not found in environment.")
            return []
        query = {
            "query": {
                "query_string": {
                    "query": f"formType:\"{form_type}\" AND ticker:\"{symbol}\""
                }
            },
            "from": "0",
            "size": limit,
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        headers = {"Content-Type": "application/json"}
        url = f"{self.base_url_sec}/v1/submissions?token={api_key}"
        data = await self._post_json(url, query, headers=headers)
        if isinstance(data, dict) and data.get("error"):
            logger.error("SEC API error (%s): %s", data.get("status"), data.get("error"))
            return []
        return data.get("submissions", []) if isinstance(data, dict) else []

    def normalize_market_snapshot(self, payload: Dict[str, Any], source: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Normalize external market data into a stable fact schema for downstream use.
        Returns a raw_content payload compatible with raw_documents.
        """
        now = datetime.now(timezone.utc).isoformat()

        def _to_decimal(value: Any) -> Optional[str]:
            if value is None:
                return None
            try:
                return format(Decimal(str(value)), "f")
            except (InvalidOperation, ValueError):
                return None

        facts = []
        if source == "finnhub_quote" and payload:
            facts.append({
                "entity": symbol,
                "metric": "price",
                "period": now[:10],
                "period_norm": now[:10],
                "raw_value": _to_decimal(payload.get("c")),
                "normalized_value": _to_decimal(payload.get("c")),
                "unit": "currency",
                "currency": "USD",
                "source": source,
                "evidence": {
                    "document_id": None,
                    "snippet": str(payload),
                    "method": "finnhub_quote",
                    "confidence": 0.9,
                },
            })
        elif source == "finnhub_crypto" and payload:
            facts.append({
                "entity": symbol,
                "metric": "crypto_price",
                "period": now[:10],
                "period_norm": now[:10],
                "raw_value": _to_decimal(payload.get("price")),
                "normalized_value": _to_decimal(payload.get("price")),
                "unit": "currency",
                "currency": "USD",
                "source": source,
                "evidence": {
                    "document_id": None,
                    "snippet": str(payload),
                    "method": "finnhub_crypto",
                    "confidence": 0.9,
                },
            })
        elif source == "fmp_financial_statement_growth" and payload:
            for item in payload:
                for key, value in item.items():
                    if "growth" in key.lower() and isinstance(value, (int, float)):
                        facts.append({
                            "entity": symbol,
                            "metric": key,
                            "period": item.get("date"),
                            "period_norm": item.get("date"),
                            "raw_value": _to_decimal(value),
                            "normalized_value": _to_decimal(value),
                            "unit": "ratio",
                            "currency": None,
                            "source": source,
                            "evidence": {
                                "document_id": None,
                                "snippet": str(item),
                                "method": "fmp_financial_statement_growth",
                                "confidence": 0.8,
                            },
                        })
        elif source == "sec_filings" and payload:
            for submission in payload:
                # Extracting relevant information from SEC submission
                filing_date = submission.get("filedAt", "")[:10]
                report_url = submission.get("linkToHtml", "")
                form_type = submission.get("formType", "")
                
                facts.append({
                    "entity": symbol,
                    "metric": f"sec_filing_{form_type}",
                    "period": filing_date,
                    "period_norm": filing_date,
                    "raw_value": report_url,
                    "normalized_value": report_url,
                    "unit": "url",
                    "currency": None,
                    "source": source,
                    "evidence": {
                        "document_id": None,
                        "snippet": f"SEC filing {form_type} on {filing_date}: {report_url}",
                        "method": "sec_filings",
                        "confidence": 0.95,
                    },
                })
        elif source == "fred_series" and payload:
            for observation in payload:
                value = observation.get("value")
                date = observation.get("date")
                series_id = observation.get("series_id") # Assuming series_id is passed in observation from fetch_fred_series
                
                if value not in (None, "", ".") and date and series_id: # Filter out missing values
                    unit = "percent" if series_id in {"FEDFUNDS", "GS10", "T10Y2Y"} or series_id.startswith("GS") else "ratio"
                    facts.append({
                        "entity": series_id,
                        "metric": series_id, # FRED series_id can serve as metric
                        "period": date,
                        "period_norm": date,
                        "raw_value": _to_decimal(value),
                        "normalized_value": _to_decimal(value),
                        "unit": unit,
                        "currency": None, # FRED data usually not currency
                        "source": source,
                        "evidence": {
                            "document_id": f"fred:{series_id}:{date}",
                            "snippet": f"FRED series {series_id} on {date}: {value}",
                            "method": "fred_series",
                            "confidence": 0.95,
                        },
                    })
        elif source == "finnhub_forex" and payload:
            rate = None
            if symbol and payload.get("quote"):
                rate = payload["quote"].get(symbol)
            facts.append({
                "entity": symbol,
                "metric": "fx_rate",
                "period": now[:10],
                "period_norm": now[:10],
                "raw_value": _to_decimal(rate),
                "normalized_value": _to_decimal(rate),
                "unit": "ratio",
                "currency": None,
                "source": source,
                "evidence": {
                    "document_id": None,
                    "snippet": str(payload),
                    "method": "finnhub_forex",
                    "confidence": 0.9,
                },
            })
        elif source == "event_timeline" and payload:
            events = payload if isinstance(payload, list) else []
            for event in events:
                event_date = event.get("date") or now[:10]
                event_type = event.get("event_type") or "event"
                headline = event.get("headline") or event.get("title") or ""
                severity = event.get("severity")
                facts.append({
                    "entity": symbol or event.get("entity") or event.get("region") or "market",
                    "metric": f"event_{event_type}",
                    "period": event_date,
                    "period_norm": event_date,
                    "raw_value": headline,
                    "normalized_value": headline,
                    "unit": "event",
                    "currency": None,
                    "source": source,
                    "evidence": {
                        "document_id": event.get("event_id"),
                        "snippet": headline,
                        "method": "event_ingest",
                        "confidence": float(event.get("confidence") or 0.8),
                        "severity": severity,
                    },
                })

        return {
            "facts": [f for f in facts if f.get("normalized_value") is not None],
            "metadata": {
                "source": source,
                "symbol": symbol,
                "captured_at": now,
            },
            "raw_payload": payload,
        }

# Singleton instance
market_data_service = MarketDataService()
