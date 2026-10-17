# Phase 2 — Market Data Contracts and Quality

This increment adds provider-neutral request/provider contracts and deterministic OHLCV batch quality scoring. It is intentionally adapter-agnostic: no external APIs, keys, or network calls are added.

## Contracts

- `MarketDataRequest` identifies a symbol, interval, time range, and bounded row limit; timestamps must be timezone-aware.
- `MarketDataProvider` is an async protocol whose adapters return normalized `Candle` values and expose a stable source identifier.
- Provider adapters do not calculate indicators, determine risk, call LLMs, or submit orders.

## Quality scoring

`score_candle_batch` rejects empty, malformed, duplicate, unordered, and future-dated input. It reports missing expected bars, irregular cadence, latest-candle age, and staleness. Completeness is weighted 60% and freshness 40% in the overall score. This score is data-quality metadata only and must never be treated as a signal or as permission to trade. The feature snapshot builder independently rejects stale data.

## Remaining work

- Implement source-specific crypto and forex adapters with rate limiting, retries, and explicit provider timestamps.
- Persist normalized candles idempotently and reconcile gaps/revisions.
- Add schema-level lineage for source, fetched-at time, interval, and data version.
- Add outage/replay tests before relying on any feed for paper trading.
