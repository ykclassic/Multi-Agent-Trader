# Phase 2 — Market Data Ingestion Reliability

## Providers and boundaries

- BinanceSpotProvider reads public Binance spot klines.
- TwelveDataForexProvider reads Twelve Data forex time series. It is a market-data provider, not the OANDA execution/pricing API.
- Both normalize candle-open timestamps to UTC, validate OHLCV, omit still-open candles, and use bounded HTTP retries and request spacing.
- The ingestion worker only validates, scores, and stores market data. It does not create signals, invoke an LLM, or submit orders.

## Forex session-aware quality

ForexSessionCalendar uses New York local sessions (Sunday 17:00 through Friday 17:00), so DST shifts are handled by zoneinfo. Weekend closure timestamps are not counted as missing candles. Forex freshness age is also measured in open-session time, not raw wall-clock time. A genuine missing candle during an open session still reduces completeness.

FX holiday and early-close schedules vary by provider and market. Configure repository Actions variables:
- FOREX_HOLIDAYS: comma-separated New York market dates, YYYY-MM-DD (full-day closures).
- FOREX_EARLY_CLOSES: comma-separated YYYY-MM-DDTHH:MM values in New York local time.
Do not assume one universal holiday calendar covers every provider. Validate these values against the selected feed's documented trading schedule.

## Canonical candles and immutable revisions

public.market_candles is the current canonical value per (instrument_id, source, timeframe_seconds, candle_at). Repeated batches upsert that row. If OHLCV changes, a database trigger increments data_version and updates updated_at.

Every observed OHLCV content is also appended to public.market_candle_revisions using a SHA-256 content hash and observed_at. The unique key includes the hash, so replaying identical data does not create duplicate revision records; a provider correction creates a new immutable row. The service role can insert revisions but cannot update/delete them. The canonical row keeps the current source_revision hash for traceability.

## Scheduled worker and circuit breaker

Two GitHub Actions workflows run on main after merge:
- Crypto: every 5 minutes; default symbols BTC/USDT,ETH/USDT, 5-minute bars, 12-hour overlap.
- Forex: hourly at minute 17; default symbol EUR/USD, 1-hour bars, 72-hour overlap. This conservative default limits Twelve Data quota usage. Expand INGEST_FOREX_SYMBOLS only after confirming the subscribed quota.

Both workflows use non-cancelling concurrency groups and job timeouts. A database-backed market_data_provider_state table persists consecutive failures and breaker-open time. HTTP 429/credit/rate-limit errors open the breaker for 60 minutes immediately; three other consecutive failures open it for 15 minutes. A successful cycle resets the breaker. Failed provider runs stop that batch and fail the workflow, making failures observable instead of silently passing.

### Required GitHub Actions secrets

Configure these repository secrets before enabling the workflows:
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY — server-only; never expose as NEXT_PUBLIC_*
- TWELVEDATA_API_KEY

Optional repository Actions variables:
- INGEST_CRYPTO_SYMBOLS, INGEST_CRYPTO_VENUE
- INGEST_FOREX_SYMBOLS, INGEST_FOREX_VENUE
- FOREX_HOLIDAYS, FOREX_EARLY_CLOSES

The workflow uses the existing registry and fails closed if the symbol/venue pair does not resolve to exactly one active instrument. Scheduled workflows start only from the default branch, so merge these changes before expecting scheduled runs.

## Operational verification

1. Apply supabase/migrations/20261017133700_market_data_reliability.sql to the target Supabase project before the first scheduled run.
2. Manually dispatch each workflow after configuring secrets.
3. Verify market_candles has rows for expected active instruments and that market_candle_revisions records distinct content hashes when provider values change.
4. Re-run the same candle window and verify no duplicate revision hashes or duplicate canonical keys.
5. Confirm Friday close to Sunday open creates zero weekend missing bars, while a removed candle inside an open session is counted.
6. Simulate HTTP 429 and repeated provider failures in tests; verify breaker persistence and cooldown behavior.

## Phase 3 entry gate

Do not proceed into quantitative/market-state engines until:
- forex weekend, DST, configured holiday, and in-session gap tests pass;
- identical replay is idempotent and a changed candle produces a distinct immutable revision;
- provider-specific scheduled workflows pass after manual dispatch;
- provider breaker state is persisted and rate limits halt further calls during cooldown;
- production has nonzero candle/revision data and data-quality outcomes are observable.

This increment still does not enable paper/live order execution.
