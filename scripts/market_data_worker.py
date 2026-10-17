"""Scheduled bounded ingestion worker with a persistent provider circuit breaker.

Run from GitHub Actions or another trusted scheduler. No signals or orders are
created. API keys and the Supabase service-role key must remain server-side.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone, date, time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from quant.market_engine.contracts import MarketDataRequest
from quant.market_engine.ingestion import ingest_candles
from quant.market_engine.persistence import SupabaseRestCandleRepository
from quant.market_engine.providers import (
    BinanceSpotProvider, MarketDataProviderError, TwelveDataForexProvider,
)
from quant.market_engine.sessions import ForexSessionCalendar
from scripts.ingest_market_data import resolve_instrument_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def configured_forex_calendar() -> ForexSessionCalendar:
    holidays = frozenset(
        date.fromisoformat(item.strip())
        for item in os.environ.get("FOREX_HOLIDAYS", "").split(",") if item.strip()
    )
    early_closes: dict[date, time] = {}
    for item in os.environ.get("FOREX_EARLY_CLOSES", "").split(","):
        if item.strip():
            day_text, time_text = item.strip().split("T", 1)
            early_closes[date.fromisoformat(day_text)] = time.fromisoformat(time_text)
    return ForexSessionCalendar(holidays=holidays, early_closes=early_closes)


class PersistentProviderCircuitBreaker:
    def __init__(self, *, supabase_url: str, service_role_key: str,
                 provider: str, failure_threshold: int = 3,
                 cooldown_minutes: int = 15) -> None:
        self.base_url = supabase_url.rstrip("/")
        self.key = service_role_key
        self.provider = provider
        self.failure_threshold = failure_threshold
        self.cooldown_minutes = cooldown_minutes

    def _request_json(self, method: str, url: str, payload=None):
        headers = {
            "apikey": self.key, "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
        }
        data = None
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode()
            headers["Content-Type"] = "application/json"
            headers["Prefer"] = "resolution=merge-duplicates,return=representation"
        request = Request(url, data=data, method=method, headers=headers)
        try:
            with urlopen(request, timeout=10) as response:
                body = response.read()
                return json.loads(body.decode()) if body else None
        except (HTTPError, URLError, UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("Provider circuit-state storage is unavailable") from None

    def read(self) -> dict:
        query = urlencode({"provider": f"eq.{self.provider}", "select": "*", "limit": "1"})
        rows = self._request_json("GET", f"{self.base_url}/rest/v1/market_data_provider_state?{query}")
        return rows[0] if isinstance(rows, list) and rows else {
            "provider": self.provider, "consecutive_failures": 0, "opened_until": None,
        }

    def _write(self, state: dict) -> None:
        query = urlencode({"on_conflict": "provider"})
        self._request_json("POST", f"{self.base_url}/rest/v1/market_data_provider_state?{query}", state)

    def ensure_closed(self) -> dict:
        state = self.read()
        opened_until = state.get("opened_until")
        if opened_until:
            opened = datetime.fromisoformat(opened_until.replace("Z", "+00:00"))
            if opened > utcnow():
                raise RuntimeError(f"Circuit open for {self.provider} until {opened.isoformat()}")
        return state

    def success(self) -> None:
        self._write({
            "provider": self.provider, "consecutive_failures": 0,
            "opened_until": None, "last_attempt_at": utcnow().isoformat(),
            "last_success_at": utcnow().isoformat(), "last_error_code": None,
            "updated_at": utcnow().isoformat(),
        })

    def failure(self, error: Exception) -> dict:
        state = self.read()
        failures = int(state.get("consecutive_failures") or 0) + 1
        message = str(error)
        rate_limited = "429" in message or "rate limit" in message.lower() or "credits" in message.lower()
        should_open = rate_limited or failures >= self.failure_threshold
        cooldown = 60 if rate_limited else self.cooldown_minutes
        now = utcnow()
        opened_until = (now + timedelta(minutes=cooldown)).isoformat() if should_open else None
        self._write({
            "provider": self.provider, "consecutive_failures": failures,
            "opened_until": opened_until, "last_attempt_at": now.isoformat(),
            "last_success_at": state.get("last_success_at"),
            "last_error_code": "rate_limited" if rate_limited else "provider_failure",
            "updated_at": now.isoformat(),
        })
        return {"consecutive_failures": failures, "opened_until": opened_until,
                "last_error_code": "rate_limited" if rate_limited else "provider_failure"}


async def run(asset_class: str) -> int:
    supabase_url = os.environ.get("SUPABASE_URL")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY as server-side secrets")

    if asset_class == "crypto":
        symbols = [s.strip().upper() for s in os.environ.get("INGEST_CRYPTO_SYMBOLS", "BTC/USDT,ETH/USDT").split(",") if s.strip()]
        venue = os.environ.get("INGEST_CRYPTO_VENUE", "BINANCE").upper()
        timeframe = 300
        lookback = timedelta(hours=12)
        provider = BinanceSpotProvider()
    else:
        symbols = [s.strip().upper() for s in os.environ.get("INGEST_FOREX_SYMBOLS", "EUR/USD").split(",") if s.strip()]
        venue = os.environ.get("INGEST_FOREX_VENUE", "OANDA").upper()
        timeframe = 3600
        lookback = timedelta(hours=72)
        provider = TwelveDataForexProvider()

    if not symbols:
        raise RuntimeError(f"No symbols configured for {asset_class}")
    repository = SupabaseRestCandleRepository.from_env()
    breaker = PersistentProviderCircuitBreaker(
        supabase_url=supabase_url, service_role_key=service_role_key,
        provider=provider.source_id,
    )
    breaker.ensure_closed()
    completed = []
    for symbol in symbols:
        instrument_id = resolve_instrument_id(
            supabase_url=supabase_url, service_role_key=service_role_key,
            symbol=symbol, venue_code=venue,
        )
        end_at = utcnow()
        request = MarketDataRequest(
            symbol=symbol, timeframe_seconds=timeframe,
            start_at=end_at - lookback, end_at=end_at,
            limit=min(5000, int(lookback.total_seconds() // timeframe) + 2),
        )
        try:
            result = await ingest_candles(
                provider=provider, request=request, instrument_id=instrument_id,
                repository=repository, market_type=asset_class,
                forex_calendar=configured_forex_calendar() if asset_class == "forex" else None,
            )
        except MarketDataProviderError as exc:
            state = breaker.failure(exc)
            print(json.dumps({
                "provider": provider.source_id, "asset_class": asset_class,
                "completed": completed, "status": "provider_failure",
                "circuit_breaker": state, "error": str(exc)[:240],
            }, indent=2))
            return 1
        completed.append({
                "symbol": symbol, "fetched_count": result.fetched_count,
                "persisted_count": result.persisted_count,
                "quality_score": result.quality.overall_quality_score,
                "missing_candle_count": result.quality.missing_candle_count,
                "quality_issues": list(result.quality.issues),
        })
    breaker.success()

    print(json.dumps({
        "provider": provider.source_id, "asset_class": asset_class,
        "venue": venue, "status": "ok", "completed": completed,
    }, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one bounded market-data ingestion cycle.")
    parser.add_argument("--asset-class", required=True, choices=("crypto", "forex"))
    args = parser.parse_args()
    try:
        return asyncio.run(run(args.asset_class))
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)[:240]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
