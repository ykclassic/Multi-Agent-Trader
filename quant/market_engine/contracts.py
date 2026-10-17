"""Provider-neutral market-data contracts for crypto and forex adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence

from .engine import Candle


@dataclass(frozen=True, slots=True)
class MarketDataRequest:
    symbol: str
    timeframe_seconds: int
    start_at: datetime
    end_at: datetime
    limit: int = 1000

    def validate(self) -> None:
        if not self.symbol.strip():
            raise ValueError("Symbol is required")
        if self.timeframe_seconds <= 0:
            raise ValueError("Timeframe must be positive")
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("Request timestamps must be timezone-aware")
        if self.start_at >= self.end_at:
            raise ValueError("start_at must be earlier than end_at")
        if self.limit < 1 or self.limit > 100_000:
            raise ValueError("Limit must be between 1 and 100000")


class MarketDataProvider(Protocol):
    """Adapters return normalized candles; they do not compute indicators or trade."""

    @property
    def source_id(self) -> str:
        """Stable identifier for the venue/provider and feed type."""
        ...

    async def fetch_ohlcv(self, request: MarketDataRequest) -> Sequence[Candle]:
        """Fetch normalized candles for a requested instrument/time range."""
        ...
