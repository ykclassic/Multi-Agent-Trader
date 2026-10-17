"""Provider-neutral OHLCV batch completeness and freshness scoring."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from .engine import Candle
from .sessions import ForexSessionCalendar


@dataclass(frozen=True, slots=True)
class MarketDataQuality:
    source: str
    candle_count: int
    missing_candle_count: int
    age_seconds: float
    is_stale: bool
    completeness_score: float
    freshness_score: float
    overall_quality_score: float
    issues: tuple[str, ...]


def score_candle_batch(
    candles: Sequence[Candle],
    *,
    source: str,
    as_of: datetime,
    timeframe_seconds: int = 3600,
    max_age_seconds: int = 180,
    market_type: str = "crypto",
    forex_calendar: ForexSessionCalendar | None = None,
) -> MarketDataQuality:
    """Score completeness/freshness; forex gaps are counted only in open sessions.

    Forex uses a configurable New York Sunday-17:00 to Friday-17:00 calendar by
    default. Holiday dates and early closes can be supplied through the calendar.
    Quality metadata is not a trading signal.
    """
    if not source.strip():
        raise ValueError("A non-empty market-data source identifier is required")
    if timeframe_seconds <= 0 or max_age_seconds < 0:
        raise ValueError("Timeframe must be positive and max age cannot be negative")
    if market_type not in ("crypto", "forex"):
        raise ValueError("market_type must be crypto or forex")
    if not candles:
        raise ValueError("At least one candle is required")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")

    for candle in candles:
        candle.validate()
    times = [c.timestamp.astimezone(timezone.utc) for c in candles]
    if any(current <= previous for previous, current in zip(times, times[1:])):
        raise ValueError("Candles must be strictly ordered by timestamp with no duplicates")

    current_time = as_of.astimezone(timezone.utc)
    age_seconds = (current_time - times[-1]).total_seconds()
    if age_seconds < 0:
        raise ValueError("Latest candle is future-dated")

    calendar = forex_calendar or ForexSessionCalendar()
    if market_type == "forex":
        age_seconds = calendar.trading_seconds_between(times[-1], current_time)
    issues: list[str] = []
    missing = 0
    for previous, current in zip(times, times[1:]):
        interval_count = (current - previous).total_seconds() / timeframe_seconds
        nearest_interval = round(interval_count)
        if abs(interval_count - nearest_interval) > 1e-6:
            issues.append("irregular_candle_cadence")
        cursor = previous + timedelta(seconds=timeframe_seconds)
        while cursor < current:
            expected = market_type == "crypto" or calendar.is_open(cursor)
            if expected:
                missing += 1
            cursor += timedelta(seconds=timeframe_seconds)
    if missing:
        issues.append(f"missing_candles:{missing}")

    is_stale = age_seconds > max_age_seconds
    if is_stale:
        issues.append("stale_latest_candle")
    completeness = len(candles) / (len(candles) + missing)
    freshness = (1.0 if age_seconds == 0 else 0.0) if max_age_seconds == 0 else max(0.0, 1.0 - age_seconds / max_age_seconds)
    overall = 0.6 * completeness + 0.4 * freshness
    return MarketDataQuality(
        source=source, candle_count=len(candles), missing_candle_count=missing,
        age_seconds=age_seconds, is_stale=is_stale,
        completeness_score=min(1.0, max(0.0, completeness)),
        freshness_score=min(1.0, max(0.0, freshness)),
        overall_quality_score=min(1.0, max(0.0, overall)),
        issues=tuple(dict.fromkeys(issues)),
    )
