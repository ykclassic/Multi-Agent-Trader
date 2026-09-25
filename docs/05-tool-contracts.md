# Tool Contracts

LLMs access domain tools, not arbitrary SQL, shell or broker credentials.

## Market tools
- get_market_snapshot(instrument, timeframe)
- get_ohlcv(instrument, timeframe, start, end)
- get_order_book(instrument, depth)
- get_spread(instrument)
- get_market_state(instrument)

## Crypto tools
- get_funding(instrument, venue)
- get_open_interest(instrument, venue)
- get_liquidations(instrument, window)
- get_onchain_metrics(asset, metrics, as_of)

## FX/macro tools
- get_economic_calendar(window)
- get_macro_series(series, as_of)
- get_central_bank_events(window)
- get_rates_context(pair, as_of)

## Research tools
- search_news(query, as_of)
- get_sentiment(asset, window, as_of)
- get_evidence(evidence_ids)

## Portfolio tools
- get_portfolio_snapshot()
- get_strategy_exposure(strategy_id)
- get_open_positions()
- get_risk_limits()

## Execution tools
Execution tools are not exposed to analyst/research agents. The execution service alone may call:
- place_order
- cancel_order
- amend_order
- get_order
- get_balances
- get_positions

## Tool result envelope
```json
{
  "data": {},
  "source": "provider",
  "observed_at": "...",
  "received_at": "...",
  "freshness_ms": 42,
  "quality_score": 0.99,
  "evidence_id": "E123"
}
```

Tool calls must be logged with trace_id, agent_run_id, latency, success/failure and schema version.
