"""Run one bounded market-data ingestion batch from a trusted server environment.

Example:
  python -m scripts.ingest_market_data --asset-class crypto --symbol BTC/USDT
  python -m scripts.ingest_market_data --asset-class forex --symbol EUR/USD
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from quant.market_engine.contracts import MarketDataRequest
from quant.market_engine.ingestion import ingest_candles
from quant.market_engine.persistence import SupabaseRestCandleRepository
from quant.market_engine.providers import BinanceSpotProvider, TwelveDataForexProvider


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamps must include a timezone, for example +00:00 or Z")
    return parsed.astimezone(timezone.utc)


def default_venue_code(asset_class: str, requested_venue: str | None = None) -> str:
    if asset_class not in ("crypto", "forex"):
        raise ValueError("asset_class must be crypto or forex")
    return (requested_venue or ("BINANCE" if asset_class == "crypto" else "OANDA")).upper()


def resolve_instrument_id(*, supabase_url: str, service_role_key: str,
                          symbol: str, venue_code: str) -> str:
    params = urlencode({
        "select": "id,symbol,instrument_type,venues!inner(code,asset_class)",
        "symbol": f"eq.{symbol}",
        "is_active": "eq.true",
        "venues.code": f"eq.{venue_code}",
        "limit": "2",
    })
    request = Request(
        f"{supabase_url.rstrip('/')}/rest/v1/instruments?{params}",
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=12) as response:
            rows = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Instrument registry lookup failed with HTTP {exc.code}") from None
    except (URLError, UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("Instrument registry lookup failed or returned invalid JSON") from None
    if not isinstance(rows, list) or len(rows) != 1 or not rows[0].get("id"):
        raise RuntimeError(
            f"Expected exactly one active instrument for symbol={symbol} venue={venue_code}; found {len(rows) if isinstance(rows, list) else 'invalid response'}"
        )
    return str(rows[0]["id"])


async def run(args: argparse.Namespace) -> int:
    supabase_url = os.environ.get("SUPABASE_URL")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in this trusted server environment")

    venue_code = default_venue_code(args.asset_class, args.venue)
    instrument_id = resolve_instrument_id(
        supabase_url=supabase_url, service_role_key=service_role_key,
        symbol=args.symbol, venue_code=venue_code,
    )
    if args.asset_class == "crypto":
        symbol_map = {args.symbol: args.provider_symbol} if args.provider_symbol else None
        provider = BinanceSpotProvider(symbol_map=symbol_map)
    else:
        if args.provider_symbol:
            raise ValueError("--provider-symbol is only supported for crypto symbol mappings")
        provider = TwelveDataForexProvider()

    end_at = args.end or datetime.now(timezone.utc)
    start_at = args.start or (end_at - timedelta(seconds=args.timeframe_seconds * args.limit))
    request = MarketDataRequest(
        symbol=args.symbol, timeframe_seconds=args.timeframe_seconds,
        start_at=start_at, end_at=end_at, limit=args.limit,
    )
    repository = SupabaseRestCandleRepository.from_env()
    result = await ingest_candles(
        provider=provider, request=request, instrument_id=instrument_id, repository=repository,
    )
    print(json.dumps({
        "source": result.source,
        "symbol": args.symbol,
        "instrument_id": result.instrument_id,
        "timeframe_seconds": result.timeframe_seconds,
        "fetched_count": result.fetched_count,
        "persisted_count": result.persisted_count,
        "quality_score": result.quality.overall_quality_score,
        "quality_issues": list(result.quality.issues),
    }, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch and persist one bounded crypto/forex candle batch.")
    parser.add_argument("--asset-class", choices=("crypto", "forex"), required=True)
    parser.add_argument("--symbol", required=True, help="Exact symbol in the instrument registry, e.g. BTC/USDT or EUR/USD")
    parser.add_argument("--venue", help="Registry venue code; defaults to BINANCE for crypto or OANDA for forex")
    parser.add_argument("--provider-symbol", help="Explicit upstream symbol override (crypto only, e.g. BTCUSDT)")
    parser.add_argument("--timeframe-seconds", type=int, default=3600)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--start", type=parse_datetime, help="Timezone-aware ISO timestamp")
    parser.add_argument("--end", type=parse_datetime, help="Timezone-aware ISO timestamp")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.timeframe_seconds <= 0 or not 1 <= args.limit <= 100_000:
        print("timeframe-seconds must be positive and limit must be between 1 and 100000", file=sys.stderr)
        return 2
    if args.start and args.end and args.start >= args.end:
        print("--start must be earlier than --end", file=sys.stderr)
        return 2
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        # Provider and repository errors are deliberately sanitized at their source.
        print(f"Market-data ingestion failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
