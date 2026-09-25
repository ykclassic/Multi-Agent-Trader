# API Contracts

## User-facing API
### Strategies
POST /api/strategies
GET /api/strategies/:id
POST /api/strategies/:id/runs

### Research
POST /api/research/runs
GET /api/research/runs/:id
GET /api/decisions/:id

### Portfolio
GET /api/portfolio
GET /api/portfolio/risk
GET /api/positions

### Backtests
POST /api/backtests
GET /api/backtests/:id

## Internal service contracts
Prefer typed events/commands over synchronous cross-service RPC for long workflows.

## Command example
```json
{
  "type": "RUN_STRATEGY",
  "strategy_version_id": "...",
  "instrument": "...",
  "requested_by": "...",
  "idempotency_key": "..."
}
```

## Security
Authenticate all user APIs. Authorize by workspace and strategy. Never expose service-role database credentials or broker credentials.
