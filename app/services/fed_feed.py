from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


_FEED_KEYS: Dict[str, Tuple[str, ...]] = {
    "dot_plot_change": (
        "dot_plot_change",
        "dot_plot_delta",
        "dot_plot_shift",
        "dot_plot_surprise",
        "fomc_dot_plot_change",
    ),
    "policy_rate": (
        "policy_rate",
        "fed_funds",
        "effective_fed_funds",
        "ffr",
    ),
    "policy_rate_change": (
        "policy_rate_change",
        "fed_funds_change",
        "ffr_change",
        "policy_rate_delta",
    ),
    "rate_expectation_change": (
        "rate_expectation_change",
        "futures_rate_change",
        "ois_change",
        "rate_path_change",
    ),
    "qt_pace": (
        "qt_pace",
        "balance_sheet_runoff",
        "qt_runoff",
    ),
    "rrp_balance": (
        "rrp_balance",
        "reverse_repo_balance",
        "rrp",
    ),
    "bank_term_funding": (
        "bank_term_funding",
        "btfp_balance",
    ),
    "liquidity_index": ("liquidity_index", "liquidity_stress"),
}


@dataclass
class FedFeedSnapshot:
    values: Dict[str, float] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""

    def age_seconds(self, now: Optional[datetime] = None) -> float:
        if now is None:
            now = datetime.now(timezone.utc)
        return max(0.0, (now - self.observed_at).total_seconds())


class FedRealTimeFeed:
    def __init__(self, stale_after_seconds: float = 3600.0) -> None:
        self._stale_after_seconds = max(60.0, float(stale_after_seconds))
        self._snapshot: Optional[FedFeedSnapshot] = None

    def update(self, payload: Dict[str, Any], observed_at: Optional[datetime] = None, source: str = "") -> None:
        if not isinstance(payload, dict):
            return
        values: Dict[str, float] = {}
        for canonical, aliases in _FEED_KEYS.items():
            val = _extract_first_float(payload, aliases)
            if val is not None:
                values[canonical] = val
        if not values:
            return
        timestamp = observed_at or datetime.now(timezone.utc)
        self._snapshot = FedFeedSnapshot(values=values, observed_at=timestamp, source=str(source or ""))

    def snapshot(self) -> Optional[FedFeedSnapshot]:
        return self._snapshot

    def is_stale(self, now: Optional[datetime] = None) -> bool:
        if self._snapshot is None:
            return True
        return self._snapshot.age_seconds(now) > self._stale_after_seconds

    def effective_delta(self, fallback_delta: float) -> Tuple[float, str]:
        if self._snapshot is None or self.is_stale():
            return fallback_delta, ""
        values = self._snapshot.values
        surprise = (
            values.get("dot_plot_change")
            if "dot_plot_change" in values
            else values.get("rate_expectation_change")
        )
        if surprise is None:
            surprise = values.get("policy_rate_change")
        if surprise is None:
            return fallback_delta, ""
        if abs(fallback_delta) < 1e-6:
            return float(surprise), "feed_override"
        blended = (0.6 * float(fallback_delta)) + (0.4 * float(surprise))
        return blended, "feed_blend"

    def liquidity_stress(self) -> float:
        if self._snapshot is None or self.is_stale():
            return 0.0
        values = self._snapshot.values
        if "liquidity_index" in values:
            return _clamp(float(values["liquidity_index"]), 0.0, 1.0)

        stress = 0.0
        qt_pace = values.get("qt_pace")
        if qt_pace is not None:
            stress += _normalize(qt_pace, scale=100.0, cap=0.6)

        rrp_balance = values.get("rrp_balance")
        if rrp_balance is not None:
            stress += _normalize(rrp_balance, scale=1500.0, cap=0.5)

        policy_rate = values.get("policy_rate")
        if policy_rate is not None:
            stress += _normalize(policy_rate, scale=6.0, cap=0.4)

        return _clamp(stress, 0.0, 1.0)


def _extract_first_float(payload: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[float]:
    for key in keys:
        if key not in payload:
            continue
        try:
            val = float(payload[key])
        except (TypeError, ValueError):
            continue
        if val == val:
            return val
    return None


def _normalize(value: float, scale: float, cap: float) -> float:
    try:
        val = abs(float(value)) / max(scale, 1e-6)
    except (TypeError, ValueError):
        return 0.0
    return _clamp(val, 0.0, cap)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(float(value), high))
