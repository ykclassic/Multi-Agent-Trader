# Execution Engine Specification

## Boundary
Only Execution Service has broker/exchange credentials.

```
TradeProposal -> Risk -> Policy -> ExecutionPlan -> Adapter -> Venue
```

## Adapter interface
```text
getMarkets()
getBalances()
getPositions()
getOrderBook()
placeOrder()
cancelOrder()
amendOrder()
getOrder()
streamOrders()
streamPositions()
```

Implement venue-specific adapters behind this interface. Crypto can use CCXT where appropriate, with native adapters where exchange-specific behavior requires them. Forex uses broker adapters.

## Order lifecycle
REQUESTED -> ACKNOWLEDGED -> OPEN -> PARTIALLY_FILLED -> FILLED
                                \\-> CANCELED/REJECTED/EXPIRED

All transitions are event-recorded.

## Safety
- Idempotency keys prevent duplicate submission.
- Orders are created from structured ExecutionPlan only.
- No free-form LLM text reaches adapters.
- Credential access is isolated.
- Reconciliation compares local state to venue state continuously.
- Mismatch creates an operational alert and can trigger a circuit breaker.
