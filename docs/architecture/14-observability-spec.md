# Observability Specification

## Trace hierarchy
```
trace_id
  -> workflow_run
    -> agent_run
      -> tool_call
        -> evidence
      -> model_call
    -> policy_decision
    -> execution_order
      -> fill
```

## Metrics
- data latency/freshness
- workflow duration
- agent latency/error rate
- tool error rate
- model cost
- decision abstention rate
- policy rejection rate
- order error rate
- reconciliation mismatch rate
- portfolio/risk metrics
- backtest runtime

## Audit
Decision-critical records are append-only. Retain prompt/model/config versions sufficient to reconstruct a decision.

## Alerts
Trigger on stale feeds, broker errors, reconciliation mismatch, abnormal slippage, circuit breakers, repeated agent failure and execution anomalies.
