# Multi-Agent Trader

AI-powered multi-asset trading desk + research terminal + portfolio/risk operating system.

## Phase 1 — Foundation

This branch establishes the production control-plane foundation defined by the architecture blueprint:

- Next.js App Router / Vercel application shell.
- Supabase Auth with server-side session handling.
- PostgreSQL domain model with RLS.
- Automatic workspace creation at signup.
- Versioned strategy registry and lifecycle.
- Crypto + forex asset, venue and instrument registry.
- Authenticated dashboard.
- CI validation for typecheck, lint and build.

### Local setup

1. Create or connect a Supabase project.
2. Apply the foundation migration in `supabase/migrations`.
3. Copy `.env.example` to `.env.local` and set the Supabase URL and publishable key.
4. Run `npm install` then `npm run dev`.

### Architecture invariant

LLMs reason. Quant systems calculate. Policy systems constrain. Execution systems trade. Databases remember.

Phase 1 intentionally contains no broker credentials, order execution, AI decision authority, or live trading path.

## Scope

Crypto and forex only. Stocks are out of scope.

## Quantitative and market-state engine

The dependency-free Python package under `quant/market_engine` provides:

- Validated OHLCV inputs and deterministic EMA, RSI, ATR, return and annualized realized-volatility features.
- A trend regime plus quality-gated market-state classification (trend, volatility and momentum).
- Candle completeness/freshness checks, with configurable forex session calendars.
- Stop-distance position sizing constrained by per-trade risk and gross notional.
- A pure portfolio risk-policy evaluator for daily loss, peak-to-equity drawdown, gross/net exposure, concentration, open risk, position count and market-data quality/freshness.

Market-state output is blocked when history is insufficient, expected candles are missing, data is stale, or its quality score is below the configured threshold. Risk evaluation fails closed for invalid numeric inputs and unsafe market-data state. Default thresholds are conservative engineering defaults and must be calibrated through historical walk-forward evaluation before being treated as production policy.

Run deterministic tests with Python 3.11+:

```bash
python -m unittest discover -s tests -v
```

CI runs the Python tests alongside the Next.js typecheck, lint and production build. The quant and risk functions are research/policy calculations only. They do not call a broker, create orders, or enable live or paper execution.


## Point-in-time portfolio state

Migration `20261018100000_point_in_time_research.sql` adds workspace-scoped portfolios and immutable portfolio snapshots. A snapshot records its effective `as_of` time separately from its database `observed_at` time, hashes the canonical state, validates position totals, and stores the positions as-of that capture. The risk adapter consumes a validated snapshot directly.

- Snapshots and walk-forward research runs are readable by workspace members under RLS.
- Snapshots and evaluation runs are written by trusted server-side jobs using `SUPABASE_SERVICE_ROLE_KEY`; authenticated clients receive no write privileges.
- A snapshot imported after a historical decision time is excluded from `latest_portfolio_snapshot_as_of`, preventing retroactive knowledge from entering a replay.
- Never put the service-role key in the browser or in the snapshot JSON file.

Example snapshot import from a trusted environment:

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="server-only-secret"
python -m scripts.persist_portfolio_snapshot --input portfolio_snapshot.json
```

The JSON document must contain `portfolio_id`, `workspace_id`, timezone-aware `as_of` and `market_data_as_of`, `source`, `base_currency`, `cash_balance`, `equity`, `daily_pnl`, `peak_equity`, `market_data_quality_score`, and a `positions` array. Each position needs `symbol`, `asset_class`, `side`, `quantity`, `mark_price`, `notional`, and `estimated_loss_at_stop`. Allowed sources are `manual_import`, `historical_replay`, and `read_only_import`; no order or broker write path is exposed.

## Historical walk-forward evaluation

The research migration adds `get_point_in_time_market_candles`, which selects each candle revision only if it was observed by the candle's close plus a bounded ingestion allowance. Later corrections are excluded. The runner stores reproducible run hashes, out-of-sample fold metrics, and condition-stratified results.

```bash
python -m scripts.run_walk_forward_research \\
  --workspace-id WORKSPACE_UUID \\
  --instrument-id INSTRUMENT_UUID \\
  --symbol BTC/USDT --asset-class crypto \\
  --timeframe-seconds 300 \\
  --start 2026-01-01T00:00:00Z --end 2026-10-01T00:00:00Z
```

Tune train/test windows and fee/slippage assumptions for the instrument and timeframe. The default EMA-regime fitter is a deterministic research baseline, not a production strategy. Walk-forward test windows do not overlap; signals use only candles available through the decision candle, and returns are scored on the following candle. Results are marked `insufficient_data` unless there are enough folds and enough observations in each required condition bucket.

Condition buckets include bull, bear, high volatility, and `liquidity_shock_proxy`. The latter uses price-return and volume spikes only; it is **not** a true liquidity-shock label. True liquidity analysis requires point-in-time spread, order-book depth, and/or market-impact data, which is not yet ingested. The currently stored live-ingestion history is too short to establish robust bull/bear/liquidity-shock calibration. Historical backfills observed today are intentionally excluded from strict point-in-time replay unless their revisions were originally observed within the allowed candle-close window.

These reports are research evidence, not automatic threshold promotion. Risk limits remain unchanged until out-of-sample coverage, sensitivity analysis, and independent review support a deliberate policy change. Live and paper execution remain disabled.
