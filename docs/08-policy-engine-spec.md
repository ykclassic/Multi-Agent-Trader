# Policy Engine Specification

The Policy Gate is the final deterministic barrier before execution.

## Checks
1. Instrument is enabled.
2. Strategy is enabled and versioned.
3. Market data is fresh and complete.
4. Required evidence exists.
5. Risk assessment passes.
6. Portfolio exposure remains within limits.
7. Broker/exchange health is acceptable.
8. Spread/slippage is acceptable.
9. Major event lockout rules are satisfied.
10. User/workspace execution permission is present.
11. Circuit breakers are clear.
12. Order is syntactically and semantically valid.
13. Idempotency key is unique.

## Decisions
- APPROVE
- REJECT
- DEFER

Every decision records all checks and configuration versions.

## Kill switches
Global and scoped switches can disable new orders while allowing cancellation/reconciliation.
