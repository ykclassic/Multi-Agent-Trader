"""Validated fetch -> quality metadata -> idempotent persistence pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .contracts import MarketDataProvider, MarketDataRequest
from .engine import Candle
from .persistence import CandleRepository
from .quality import MarketDataQuality, score_candle_batch


@dataclass(frozen=True, slots=True)
class IngestionResult:
    source: str
    instrument_id: str
    timeframe_seconds: int
    fetched_count: int
    persisted_count: int
    quality: MarketDataQuality


async def ingest_candles(*, provider: MarketDataProvider, request: MarketDataRequest,
                         instrument_id: str, repository: CandleRepository,
                         clock: Callable[[], datetime] | None = None) -> IngestionResult:
    """Fetch, validate and upsert closed candles; never returns a trading signal."""
    request.validate()
    if not instrument_id.strip():
        raise ValueError("instrument_id is required")
    candles = list(await provider.fetch_ohlcv(request))
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Ingestion clock must return a timezone-aware datetime")
    now = now.astimezone(timezone.utc)
    previous: datetime | None = None
    for candle in candles:
        candle.validate()
        timestamp = candle.timestamp.astimezone(timezone.utc)
        if previous is not None and timestamp <= previous:
            raise ValueError("Provider returned unordered or duplicate candles")
        if timestamp.timestamp() + request.timeframe_seconds > now.timestamp():
            raise ValueError("Provider returned an unclosed candle")
        previous = timestamp

    if candles:
        quality = score_candle_batch(
            candles, source=provider.source_id,
            as_of=min(request.end_at.astimezone(timezone.utc), now),
            timeframe_seconds=request.timeframe_seconds,
            max_age_seconds=max(request.timeframe_seconds * 2, 180),
        )
        quality_score = quality.overall_quality_score
    else:
        quality = MarketDataQuality(
            source=provider.source_id, candle_count=0, missing_candle_count=0,
            age_seconds=0.0, is_stale=True, completeness_score=0.0,
            freshness_score=0.0, overall_quality_score=0.0,
            issues=("empty_candle_batch",),
        )
        quality_score = 0.0

    persisted = await repository.upsert_candles(
        instrument_id=instrument_id, source=provider.source_id,
        timeframe_seconds=request.timeframe_seconds, candles=candles,
        quality_score=quality_score,
    )
    return IngestionResult(
        source=provider.source_id, instrument_id=instrument_id,
        timeframe_seconds=request.timeframe_seconds, fetched_count=len(candles),
        persisted_count=persisted, quality=quality,
    )
