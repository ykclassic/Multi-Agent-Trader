# Phase 2 — Live Market-Data Adapters and Candle Storage

## Providers

- BinanceSpotProvider reads public Binance spot klines; no exchange key is required for this read-only endpoint.
- TwelveDataForexProvider reads forex time series and requires the server-side TWELVEDATA_API_KEY.
- Both normalize candle-open timestamps to UTC, validate OHLCV values, sort output, enforce request windows, and omit still-open candles.
- JsonHttpClient bounds concurrency, spaces requests, applies timeouts and retries 429/5xx/network errors with capped exponential backoff, and sanitizes upstream failures.
- The provider contract remains read-only. Neither adapter creates signals, accesses LLMs, nor submits orders.

The existing registry labels BTC/USD and ETH/USD on Binance, while Binance spot instruments are USDT-quoted. The adapter explicitly maps these labels to BTCUSDT/ETHUSDT for development; this is a USDT-market proxy and must not be presented as an exact USD quote. Production venue/instrument records should use provider-accurate symbols before strategy or accounting use.

Twelve Data is a third-party forex data source, not the OANDA execution/pricing API. EUR/USD, GBP/USD, and other supported pairs are requested by symbol. Forex spot feeds generally do not have centralized traded volume, so missing volume is represented as zero/unavailable rather than invented.

## Persistence

public.market_candles stores normalized closed OHLCV with instrument ID, provider/source, timeframe, candle-open time, fetch time, source timestamp/revision, quality score and data version. Its unique key (instrument_id, source, timeframe_seconds, candle_at) makes repeated fetches idempotent and allows provider corrections to update the current row. It does not yet retain immutable revision history; that belongs in the replay/backtesting increment.

The REST repository uses SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY only in a server-side worker. Never expose the service-role key through NEXT_PUBLIC_*, browser bundles, client code, or logs. Signed-in app users can read shared candles; browser users cannot insert or revise them. Only the server service role writes market data.

## Running ingestion

Set the following in a trusted worker environment (not the browser):
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- TWELVEDATA_API_KEY for forex

Instantiate the provider and SupabaseRestCandleRepository.from_env(), then call ingest_candles(provider=..., request=..., instrument_id=..., repository=...). The instrument ID must be resolved from the database registry, not supplied by untrusted clients.

This increment provides adapters and a callable ingestion pipeline. It does not yet schedule a recurring worker, populate production candles automatically, or enable live/paper orders. Deploy a scheduled worker only after provider quotas, instrument mappings, secrets, and Supabase grants are verified.


## One-shot ingestion CLI

From the repository root, in a trusted environment with the server-side variables set:

\`\`\`bash
export SUPABASE_URL="https://YOUR_PROJECT.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="YOUR_SERVER_ONLY_SERVICE_ROLE_KEY"
export TWELVEDATA_API_KEY="YOUR_TWELVE_DATA_KEY" # forex only

python -m scripts.ingest_market_data --asset-class crypto --symbol BTC/USD --timeframe-seconds 3600 --limit 100
python -m scripts.ingest_market_data --asset-class forex --symbol EUR/USD --timeframe-seconds 3600 --limit 100
\`\`\`

The CLI resolves the exact active instrument ID from the registry and venue before fetching. It prints counts and quality metadata, not secrets. Use a supported timeframe for the chosen provider; for a symbol whose venue market differs from the registry label, pass an explicit crypto \`--provider-symbol\` (for example \`BTCUSDT\`) and treat the quote-currency mismatch carefully. This is a one-shot bounded run, not a scheduler.
