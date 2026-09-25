# Event Schema

## Envelope
```json
{
  "event_id": "...",
  "event_type": "MARKET_SNAPSHOT_READY",
  "event_version": 1,
  "occurred_at": "...",
  "produced_at": "...",
  "trace_id": "...",
  "run_id": "...",
  "source": "...",
  "payload": {}
}
```

## Core events
MARKET_OBSERVATION_RECEIVED
MARKET_SNAPSHOT_READY
DECISION_RUN_REQUESTED
ANALYST_RUN_COMPLETED
RESEARCH_COMPLETED
TRADE_PROPOSAL_CREATED
RISK_ASSESSMENT_COMPLETED
POLICY_DECISION_MADE
EXECUTION_ORDER_REQUESTED
ORDER_ACKNOWLEDGED
ORDER_FILLED
ORDER_CANCELED
RECONCILIATION_MISMATCH
CIRCUIT_BREAKER_TRIGGERED
BACKTEST_STARTED
BACKTEST_COMPLETED

Events are versioned, idempotent and traceable.
