# Testing Strategy

## Unit
Test deterministic calculations, schemas, risk limits, freshness logic, idempotency, adapters and state transitions.

## Contract
Validate every tool, event, broker adapter and LLM structured-output schema.

## Integration
Replay complete workflows against deterministic fixtures and fake venues.

## Agent evaluation
Measure evidence attribution accuracy, unsupported-claim rate, abstention correctness, output-schema validity and consistency.

## Backtest validation
Use point-in-time fixtures and known-answer scenarios for leakage detection. Test fees, spreads, funding, latency, partial fills and corporate/macro revision timing where relevant.

## Execution safety
A test order must prove:
- no duplicate submission on retry;
- policy rejection blocks adapter invocation;
- stale data blocks execution;
- kill switch blocks new orders;
- reconciliation detects mismatched positions.

## CI gates
No production execution code merges without passing schema, risk, adapter, replay and security tests.
