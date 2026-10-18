"""HTTP market-data adapters for Binance spot and Twelve Data forex.

Adapters normalize provider payloads into UTC Candle objects and never calculate
signals, choose trades, or submit orders. Secrets are read only from the
server-side environment and are never included in raised errors.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .contracts import MarketDataRequest
from .engine import Candle


class MarketDataProviderError(RuntimeError):
    """Sanitized upstream or provider-response error."""


class JsonClient(Protocol):
    async def get_json(self, url: str, params: Mapping[str, str]) -> Any: ...


class _RetryableHttpError(RuntimeError):
    def __init__(self, status: int, retry_after: float | None = None) -> None:
        self.status = status
        self.retry_after = retry_after
        super().__init__(f"Upstream HTTP status {status}")


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, min(float(value), 30.0))
    except ValueError:
        try:
            target = parsedate_to_datetime(value)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            return max(0.0, min((target - datetime.now(timezone.utc)).total_seconds(), 30.0))
        except (TypeError, ValueError, OverflowError):
            return None


class JsonHttpClient:
    """Stdlib-only HTTP client with bounded concurrency, spacing and retries."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 12.0,
        max_retries: int = 3,
        min_interval_seconds: float = 0.15,
        concurrency: int = 2,
    ) -> None:
        if timeout_seconds <= 0 or max_retries < 0 or min_interval_seconds < 0 or concurrency < 1:
            raise ValueError("Invalid HTTP client limits")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.min_interval_seconds = min_interval_seconds
        self._semaphore = asyncio.Semaphore(concurrency)
        self._spacing_lock = asyncio.Lock()
        self._next_request_at = 0.0

    async def _space_request(self) -> None:
        async with self._spacing_lock:
            now = asyncio.get_running_loop().time()
            delay = max(0.0, self._next_request_at - now)
            self._next_request_at = max(now, self._next_request_at) + self.min_interval_seconds
        if delay:
            await asyncio.sleep(delay)

    def _read_json_sync(self, url: str) -> Any:
        request = Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Multi-Agent-Trader/0.1 market-data-ingestion",
        })
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise _RetryableHttpError(exc.code, _retry_after_seconds(exc.headers.get("Retry-After"))) from None
        except URLError:
            raise MarketDataProviderError("Market-data provider is unreachable") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise MarketDataProviderError("Market-data provider returned invalid JSON") from None

    async def get_json(self, url: str, params: Mapping[str, str]) -> Any:
        query = urlencode(params)
        target = f"{url}?{query}" if query else url
        async with self._semaphore:
            for attempt in range(self.max_retries + 1):
                await self._space_request()
                try:
                    return await asyncio.to_thread(self._read_json_sync, target)
                except _RetryableHttpError as exc:
                    retryable = 500 <= exc.status <= 599
                    if not retryable or attempt >= self.max_retries:
                        raise MarketDataProviderError(
                            f"Market-data provider returned HTTP {exc.status}"
                        ) from None
                    delay = exc.retry_after
                except MarketDataProviderError:
                    if attempt >= self.max_retries:
                        raise
                    delay = None
                if delay is None:
                    delay = min(0.5 * (2 ** attempt), 4.0)
                await asyncio.sleep(delay)
        raise MarketDataProviderError("Market-data request exhausted retries")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Provider timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _parse_timestamp(value: str | int | float) -> datetime:
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


_BINANCE_INTERVALS = {
    60: "1m", 180: "3m", 300: "5m", 900: "15m", 1800: "30m",
    3600: "1h", 7200: "2h", 14400: "4h", 21600: "6h",
    28800: "8h", 43200: "12h", 86400: "1d", 259200: "3d",
    604800: "1w", 2592000: "1M",
}
_TWELVEDATA_INTERVALS = {
    60: "1min", 300: "5min", 900: "15min", 1800: "30min",
    3600: "1h", 14400: "4h", 86400: "1day", 604800: "1week",
    2592000: "1month",
}


class BinanceSpotProvider:
    """Public Binance spot klines; the BTC/USD mappings below are USDT proxies."""

    source_id = "binance_spot_klines"
    endpoint = "https://data-api.binance.vision/api/v3/klines"

    def __init__(self, *, client: JsonClient | None = None,
                 symbol_map: Mapping[str, str] | None = None, clock=None) -> None:
        self.client = client or JsonHttpClient()
        self.symbol_map = {
            "BTC/USD": "BTCUSDT", "ETH/USD": "ETHUSDT",
            "BTC/USDT": "BTCUSDT", "ETH/USDT": "ETHUSDT",
            **{key.upper(): value.upper() for key, value in (symbol_map or {}).items()},
        }
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    async def fetch_ohlcv(self, request: MarketDataRequest) -> Sequence[Candle]:
        request.validate()
        interval = _BINANCE_INTERVALS.get(request.timeframe_seconds)
        if interval is None:
            raise ValueError("Unsupported Binance candle timeframe")
        symbol = self.symbol_map.get(
            request.symbol.upper(),
            request.symbol.upper().replace("/", "").replace("-", ""),
        )
        if not symbol.isalnum():
            raise ValueError("Invalid Binance symbol")
        now = _utc(self.clock())
        start_at = _utc(request.start_at)
        end_at = min(_utc(request.end_at), now)
        if start_at >= end_at:
            return []
        cursor_ms = int(start_at.timestamp() * 1000)
        end_ms = int(end_at.timestamp() * 1000)
        timeframe_ms = request.timeframe_seconds * 1000
        candles: list[Candle] = []

        while cursor_ms < end_ms and len(candles) < request.limit:
            page_limit = min(1000, request.limit - len(candles))
            payload = await self.client.get_json(self.endpoint, {
                "symbol": symbol, "interval": interval,
                "startTime": str(cursor_ms), "endTime": str(end_ms - 1),
                "limit": str(page_limit),
            })
            if not isinstance(payload, list):
                raise MarketDataProviderError("Binance returned an unexpected candle payload")
            if not payload:
                break
            for row in payload:
                if not isinstance(row, list) or len(row) < 6:
                    raise MarketDataProviderError("Binance returned a malformed candle")
                timestamp = _parse_timestamp(row[0])
                if not (start_at <= timestamp < end_at):
                    continue
                if timestamp.timestamp() + request.timeframe_seconds > now.timestamp():
                    continue
                candle = Candle(timestamp, float(row[1]), float(row[2]), float(row[3]),
                                float(row[4]), float(row[5]))
                candle.validate()
                candles.append(candle)
            last_open_ms = int(payload[-1][0])
            next_cursor = last_open_ms + timeframe_ms
            if next_cursor <= cursor_ms or len(payload) < page_limit:
                break
            cursor_ms = next_cursor
        candles.sort(key=lambda candle: candle.timestamp)
        return candles[:request.limit]


class TwelveDataForexProvider:
    """Twelve Data forex time series; requires the server-side TWELVEDATA_API_KEY."""

    source_id = "twelvedata_forex_time_series"
    endpoint = "https://api.twelvedata.com/time_series"

    def __init__(self, *, api_key: str | None = None,
                 client: JsonClient | None = None, clock=None) -> None:
        self.api_key = api_key or os.environ.get("TWELVEDATA_API_KEY")
        self.client = client or JsonHttpClient(min_interval_seconds=float(os.environ.get("TWELVEDATA_MIN_INTERVAL_SECONDS", "10")), concurrency=1)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    async def fetch_ohlcv(self, request: MarketDataRequest) -> Sequence[Candle]:
        request.validate()
        if not self.api_key:
            raise MarketDataProviderError("TWELVEDATA_API_KEY is required for forex market data")
        interval = _TWELVEDATA_INTERVALS.get(request.timeframe_seconds)
        if interval is None:
            raise ValueError("Unsupported Twelve Data candle timeframe")
        now = _utc(self.clock())
        start_at = _utc(request.start_at)
        end_at = min(_utc(request.end_at), now)
        if start_at >= end_at:
            return []
        payload = await self.client.get_json(self.endpoint, {
            "symbol": request.symbol.upper(), "interval": interval,
            "start_date": start_at.strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": end_at.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": "UTC", "outputsize": str(min(request.limit, 5000)),
            "apikey": self.api_key,
        })
        if not isinstance(payload, dict):
            raise MarketDataProviderError("Twelve Data returned an unexpected candle payload")
        if payload.get("status") == "error" or "values" not in payload:
            message = str(payload.get("message", "unknown provider error"))[:160]
            raise MarketDataProviderError(f"Twelve Data rejected the request: {message}")
        values = payload["values"]
        if not isinstance(values, list):
            raise MarketDataProviderError("Twelve Data returned a malformed candle list")
        candles: list[Candle] = []
        for row in values:
            try:
                timestamp = _parse_timestamp(str(row["datetime"]))
                if not (start_at <= timestamp < end_at):
                    continue
                if timestamp.timestamp() + request.timeframe_seconds > now.timestamp():
                    continue
                candle = Candle(
                    timestamp, float(row["open"]), float(row["high"]),
                    float(row["low"]), float(row["close"]), float(row.get("volume") or 0),
                )
                candle.validate()
            except (KeyError, TypeError, ValueError, OverflowError):
                raise MarketDataProviderError("Twelve Data returned a malformed candle") from None
            candles.append(candle)
        candles.sort(key=lambda candle: candle.timestamp)
        return candles[:request.limit]
