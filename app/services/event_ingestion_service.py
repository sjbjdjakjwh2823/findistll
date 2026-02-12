import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from app.api.v1.ingest import (
    get_db,
    insert_raw_document,
    update_document_status,
)
from app.services.market_data import market_data_service
from app.services.spokes import build_rag_context, extract_graph_triples
from app.services.spoke_ab_service import SpokeABService
from app.core.tenant_context import get_effective_tenant_id
from app.services.types import DistillResult

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_csv_env(name: str) -> List[str]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


async def _fetch_text(url: str, *, timeout_s: int = 20) -> str:
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers={"User-Agent": "Preciso/1.0 (event-ingestor)"}) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"event_source_fetch_failed {resp.status}: {text[:200]}")
            return await resp.text()


def _parse_rss(xml_text: str, *, limit: int = 25) -> List[Dict[str, Any]]:
    """
    Minimal RSS/Atom parser without extra deps.
    Produces event objects for /market/event ingestion.
    """
    import re

    def _tag_items(tag: str, s: str) -> List[str]:
        return re.findall(rf"<{tag}[^>]*>(.*?)</{tag}>", s, flags=re.IGNORECASE | re.DOTALL)

    items = []
    # Try RSS <item>, then Atom <entry>
    blocks = re.findall(r"<item[^>]*>(.*?)</item>", xml_text, flags=re.IGNORECASE | re.DOTALL)
    if not blocks:
        blocks = re.findall(r"<entry[^>]*>(.*?)</entry>", xml_text, flags=re.IGNORECASE | re.DOTALL)
    for block in blocks[:limit]:
        titles = _tag_items("title", block)
        links = _tag_items("link", block)
        # Atom links are often <link href="..."/>
        if not links:
            m = re.search(r"<link[^>]*href=[\"']([^\"']+)[\"']", block, flags=re.IGNORECASE)
            if m:
                links = [m.group(1)]
        pubs = _tag_items("pubDate", block) or _tag_items("published", block) or _tag_items("updated", block)
        title = (titles[0].strip() if titles else "")[:500]
        link = (links[0].strip() if links else "")[:1000]
        pub = pubs[0].strip() if pubs else _utc_now_iso()
        # Best-effort normalize date to YYYY-MM-DD
        date = None
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", pub)
        if m:
            date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        items.append(
            {
                "event_id": link or f"rss:{hash(title)}",
                "date": date or _utc_now_iso()[:10],
                "event_type": "news",
                "headline": title,
                "confidence": 0.75,
                "severity": "medium",
                "link": link,
                "source": "rss",
            }
        )
    return items


async def fetch_gdelt_events(query: str, *, max_events: int = 25) -> List[Dict[str, Any]]:
    """
    GDELT 2.1 DOC API (no key required for basic usage).
    """
    import urllib.parse
    q = urllib.parse.quote_plus(query)
    url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={q}&mode=ArtList&format=json&maxrecords={max_events}&sort=HybridRel"
    data_text = await _fetch_text(url, timeout_s=25)
    try:
        import json
        data = json.loads(data_text)
    except Exception:
        return []
    arts = (data.get("articles") or []) if isinstance(data, dict) else []
    out: List[Dict[str, Any]] = []
    for a in arts[:max_events]:
        title = (a.get("title") or "")[:500]
        link = (a.get("url") or "")[:1000]
        seen = a.get("seendate") or ""
        m = None
        if isinstance(seen, str):
            import re
            m = re.search(r"(\d{4})(\d{2})(\d{2})", seen)
        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else _utc_now_iso()[:10]
        out.append(
            {
                "event_id": link or f"gdelt:{hash(title)}",
                "date": date,
                "event_type": "news",
                "headline": title,
                "confidence": 0.7,
                "severity": "medium",
                "link": link,
                "source": "gdelt",
            }
        )
    return out


@dataclass
class EventIngestStats:
    docs_created: int = 0
    events_ingested: int = 0
    failures: int = 0


class EventIngestionService:
    async def ingest_events(self, *, symbol: Optional[str], events: List[Dict[str, Any]]) -> Optional[str]:
        if not events:
            return None

        db = get_db()
        normalized = market_data_service.normalize_market_snapshot(events, "event_timeline", symbol=symbol)
        doc_data = {
            "source": "event_timeline",
            "ticker": symbol,
            "document_type": "event_timeline",
            "document_date": None,
            "content": normalized,
            "metadata": {"symbol": symbol, "captured_at": normalized.get("metadata", {}).get("captured_at")},
        }
        doc_id = insert_raw_document(db, doc_data)
        update_document_status(db, doc_id, "completed")

        # Push to Spoke C/D stores so AI Brain can consume timeline evidence.
        try:
            distill = DistillResult(facts=normalized.get("facts") or [], cot_markdown="", metadata={"doc_id": doc_id, "source": "event_timeline"})
            contexts = build_rag_context(distill, case_id=str(doc_id))
            if contexts:
                db.save_rag_context(str(doc_id), contexts)
            triples = extract_graph_triples(distill)
            if triples:
                db.save_graph_triples(str(doc_id), triples)
            try:
                tenant_id = get_effective_tenant_id()
                service = SpokeABService()
                artifacts = service.build_spoke_b_parquets(
                    tenant_id=tenant_id,
                    doc_id=str(doc_id),
                    distill=distill,
                    normalized=normalized,
                )
                service.save_spoke_b_artifacts(db, doc_id=str(doc_id), artifacts=artifacts)
            except Exception:
                logger.exception("Event spoke B artifact build failed")
        except Exception:
            logger.exception("Event spoke C/D sync failed")

        return doc_id

    async def run_once(self) -> EventIngestStats:
        stats = EventIngestStats()
        symbol = (os.getenv("EVENT_DEFAULT_SYMBOL") or "").strip() or None

        # 1) RSS feeds
        feeds = _split_csv_env("EVENT_RSS_FEEDS")
        for feed in feeds:
            try:
                xml_text = await _fetch_text(feed)
                events = _parse_rss(xml_text, limit=int(os.getenv("EVENT_RSS_MAX", "25") or "25"))
                doc_id = await self.ingest_events(symbol=symbol, events=events)
                if doc_id:
                    stats.docs_created += 1
                    stats.events_ingested += len(events)
            except Exception:
                stats.failures += 1
                logger.exception("RSS event ingest failed for %s", feed)

        # 2) GDELT (optional)
        if os.getenv("GDELT_ENABLED", "0") == "1":
            query = (os.getenv("GDELT_QUERY") or "regulation OR sanctions OR central bank OR treasury yield").strip()
            try:
                events = await fetch_gdelt_events(query, max_events=int(os.getenv("GDELT_MAX", "25") or "25"))
                doc_id = await self.ingest_events(symbol=symbol, events=events)
                if doc_id:
                    stats.docs_created += 1
                    stats.events_ingested += len(events)
            except Exception:
                stats.failures += 1
                logger.exception("GDELT event ingest failed")

        return stats

    async def run_forever(self) -> None:
        interval_s = int(os.getenv("EVENT_INGEST_INTERVAL_S", "900") or "900")
        jitter_s = int(os.getenv("EVENT_INGEST_JITTER_S", "30") or "30")
        rng = __import__("random").Random(42)
        while True:
            start = time.time()
            try:
                stats = await self.run_once()
                logger.info("event_ingest stats=%s", stats)
            except Exception:
                logger.exception("event_ingest run failed")

            elapsed = time.time() - start
            sleep_s = max(1, interval_s - int(elapsed)) + rng.randrange(0, max(1, jitter_s))
            await asyncio.sleep(sleep_s)
