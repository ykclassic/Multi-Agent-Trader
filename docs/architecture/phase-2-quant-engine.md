# Phase 2 — Deterministic Quant Engine

## Scope of this increment

This PR establishes the first tested, pure-Python vertical slice of the quant engine. It is deliberately deterministic and independent of LLMs, network services, database access, and order execution.

### Input contract

- OHLCV candles must use timezone-aware timestamps and finite, positive OHLC prices.
- High/low must enclose open and close; volume cannot be negative.
- Candles must be strictly time-ordered and unique.
- A snapshot requires at least 27 observations for EMA(12), EMA(26), RSI(14), ATR(14), and 24-return volatility.
- Future-dated and stale latest candles are rejected. The feed adapter is responsible for only supplying closed candles.

### Output contract

- Last close, one-period and 24-period returns.
- EMA(12), EMA(26), RSI(14), ATR(14), annualized realized volatility.
- Transparent trend_up, trend_down, or range label using a small EMA separation threshold.
- Timestamp, freshness age, and candle count to support provenance and debugging.

### Risk sizing contract

The sizing function bounds quantity by both a configured equity-risk budget and gross-notional cap. It rejects invalid equity/prices, unsupported side, risk fraction above 2%, notional fraction above 100%, and stops on the wrong side of entry. This is a pre-trade sizing primitive, not the full portfolio Risk Engine.

## Explicitly not included yet

- Live exchange or forex market-data connectors.
- OHLCV persistence, feed gap detection, retry/reconciliation, and source quality scoring.
- Multi-asset portfolio state, correlation/concentration limits, leverage/margin and FX conversion.
- Backtesting, paper trading, order routing, broker credentials, or live execution.

## Verification

Run `python -m unittest discover -s tests -v`. GitHub Actions runs these tests in addition to the Next.js typecheck, lint, and production build. Tests cover determinism, uptrend classification, stale/future data rejection, ordering/OHLCV validation, risk-budget sizing, and invalid stop/risk settings.

## Next Phase 2 increments

1. Define typed provider-neutral market-data interfaces for crypto and forex.
2. Add idempotent OHLCV ingestion, persistence migrations, candle completeness checks, and freshness/quality scoring.
3. Add deterministic portfolio exposure and drawdown limits, including FX conversion and crypto venue-specific constraints.
4. Add fixtures and replay tests for gaps, duplicate candles, out-of-order events, and provider outages.
5. Keep LLMs out of feature calculations and risk enforcement; they may explain results but cannot override policy decisions.
