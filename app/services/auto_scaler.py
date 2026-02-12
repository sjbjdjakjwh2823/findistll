from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List

from app.services.feature_flags import set_flag
from app.services.metrics_logger import MetricsLogger

logger = logging.getLogger(__name__)


class PerformanceAutoScaler:
    def __init__(self) -> None:
        if "AUTO_SCALE_ENABLED" in os.environ:
            self.enabled = os.getenv("AUTO_SCALE_ENABLED", "0") == "1"
        else:
            # Default ON in prod (auto-enable performance helpers when latency degrades),
            # default OFF in dev to avoid surprising behavior during local iteration.
            self.enabled = os.getenv("APP_ENV", "dev").lower() == "prod"
        self.interval_s = int(os.getenv("AUTO_SCALE_INTERVAL_S", "30"))
        self.window_min = int(os.getenv("AUTO_SCALE_WINDOW_MIN", "10"))
        self.p95_threshold_ms = int(os.getenv("AUTO_SCALE_RAG_P95_MS", "1500"))
        self.cooldown_s = int(os.getenv("AUTO_SCALE_COOLDOWN_S", "300"))
        self.active = False
        self._last_action = 0.0

    def _percentile(self, values: List[float], pct: float) -> float:
        if not values:
            return 0.0
        values = sorted(values)
        k = max(0, min(len(values) - 1, int(round((pct / 100.0) * (len(values) - 1)))))
        return float(values[k])

    def _fetch_rag_latency_p95(self) -> float:
        client = MetricsLogger()._get_client()  # noqa: SLF001
        if not client:
            return 0.0
        since = (datetime.now(timezone.utc) - timedelta(minutes=self.window_min)).isoformat()
        rows = (
            client.table("perf_metrics")
            .select("value,created_at")
            .eq("name", "rag.latency_ms")
            .gte("created_at", since)
            .limit(5000)
            .execute()
            .data
            or []
        )
        values = [float(r.get("value") or 0) for r in rows if r.get("value") is not None]
        return self._percentile(values, 95.0)

    def _apply_scale_up(self) -> None:
        set_flag("rag_cache_enabled", True)
        set_flag("rag_rerank_enabled", True)
        set_flag("rag_compress_enabled", True)
        logger.warning("AutoScale ON: enabled rag_cache/rerank/compress")

    def _apply_scale_down(self) -> None:
        set_flag("rag_cache_enabled", False)
        set_flag("rag_rerank_enabled", False)
        set_flag("rag_compress_enabled", False)
        logger.warning("AutoScale OFF: disabled rag_cache/rerank/compress")

    async def run(self) -> None:
        if not self.enabled:
            logger.info("AutoScale disabled")
            return
        logger.info("AutoScale started (p95 threshold %sms)", self.p95_threshold_ms)
        while True:
            try:
                p95 = self._fetch_rag_latency_p95()
                now = asyncio.get_event_loop().time()
                if now - self._last_action < self.cooldown_s:
                    await asyncio.sleep(self.interval_s)
                    continue
                if p95 >= self.p95_threshold_ms and not self.active:
                    self._apply_scale_up()
                    self.active = True
                    self._last_action = now
                elif p95 < (self.p95_threshold_ms * 0.6) and self.active:
                    # Hysteresis: scale down only when well below threshold.
                    self._apply_scale_down()
                    self.active = False
                    self._last_action = now
            except Exception:
                logger.exception("AutoScale loop error")
            await asyncio.sleep(self.interval_s)
