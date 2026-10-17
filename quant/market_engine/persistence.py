"""Server-side Supabase REST persistence for normalized market candles."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .engine import Candle


class CandlePersistenceError(RuntimeError):
    """Sanitized storage error without request headers or credentials."""


class CandleRepository:
    async def upsert_candles(self, *, instrument_id: str, source: str,
                             timeframe_seconds: int, candles: Sequence[Candle],
                             quality_score: float) -> int:
        raise NotImplementedError


class SupabaseRestCandleRepository(CandleRepository):
    """Upsert candles through PostgREST using a server-only service role key."""

    table = "market_candles"
    conflict_columns = "instrument_id,source,timeframe_seconds,candle_at"

    def __init__(self, *, supabase_url: str, service_role_key: str,
                 timeout_seconds: float = 15.0) -> None:
        if not supabase_url.startswith("https://") or not service_role_key.strip():
            raise ValueError("A valid Supabase URL and server-only service key are required")
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "SupabaseRestCandleRepository":
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise CandlePersistenceError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for server-side candle persistence"
            )
        return cls(supabase_url=url, service_role_key=key)

    def _post_batch(self, rows: list[dict[str, Any]]) -> None:
        query = urlencode({"on_conflict": self.conflict_columns})
        request = Request(
            f"{self.supabase_url}/rest/v1/{self.table}?{query}",
            data=json.dumps(rows, separators=(",", ":")).encode("utf-8"),
            method="POST",
            headers={
                "apikey": self.service_role_key,
                "Authorization": f"Bearer {self.service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                if response.status not in (200, 201, 204):
                    raise CandlePersistenceError(f"Supabase returned HTTP {response.status}")
        except HTTPError as exc:
            raise CandlePersistenceError(f"Supabase candle upsert failed with HTTP {exc.code}") from None
        except URLError:
            raise CandlePersistenceError("Supabase candle storage is unreachable") from None

    async def upsert_candles(self, *, instrument_id: str, source: str,
                             timeframe_seconds: int, candles: Sequence[Candle],
                             quality_score: float) -> int:
        if not instrument_id.strip() or not source.strip() or timeframe_seconds <= 0:
            raise ValueError("Instrument, source, and positive timeframe are required")
        if not 0 <= quality_score <= 1:
            raise ValueError("Quality score must be between 0 and 1")
        if not candles:
            return 0
        fetched_at = datetime.now(timezone.utc).isoformat()
        rows: list[dict[str, Any]] = []
        previous: datetime | None = None
        for candle in candles:
            candle.validate()
            timestamp = candle.timestamp.astimezone(timezone.utc)
            if previous is not None and timestamp <= previous:
                raise ValueError("Candles must be strictly ordered with no duplicates")
            previous = timestamp
            rows.append({
                "instrument_id": instrument_id, "source": source,
                "timeframe_seconds": timeframe_seconds, "candle_at": timestamp.isoformat(),
                "open": candle.open, "high": candle.high, "low": candle.low,
                "close": candle.close, "volume": candle.volume,
                "fetched_at": fetched_at, "source_timestamp": timestamp.isoformat(),
                "source_revision": None, "quality_score": round(quality_score, 4),
                "data_version": 1, "is_closed": True,
            })
        for offset in range(0, len(rows), 500):
            await asyncio.to_thread(self._post_batch, rows[offset:offset + 500])
        return len(rows)
