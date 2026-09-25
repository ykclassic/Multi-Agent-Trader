# Domain Model

## Core entities
- Workspace: isolation boundary for users, strategies, credentials and audit records.
- Strategy: versioned trading hypothesis with required data, agents, risk and execution policy.
- Asset: canonical crypto asset or currency.
- Instrument: tradable venue-specific representation (spot, perpetual, future, forex instrument).
- Venue: exchange or broker.
- MarketSnapshot: point-in-time canonical view used by a decision.
- MarketObservation: raw/normalized observation with source and timestamps.
- MarketEvent: news, macro release, liquidation, funding event or other event.
- Feature: deterministic calculation derived from observations.
- Evidence: atomic factual/calc/inference support item.
- AgentRun: one invocation of an agent against a specific state.
- AnalystReport: typed specialist output.
- Debate: bounded adversarial research protocol.
- TradeProposal: non-executable proposal from Trader.
- RiskAssessment: deterministic risk result plus qualitative risk debate.
- PolicyDecision: deterministic approval/rejection/defer result.
- ExecutionOrder: broker/exchange order lifecycle.
- Fill: actual execution.
- Position: reconciled venue position.
- PortfolioSnapshot: point-in-time aggregate portfolio state.
- BacktestRun: immutable replay configuration and results.
- PromptVersion/ModelVersion/StrategyVersion: reproducibility metadata.

## Truth classes
Every material datum is labelled:
- OBSERVED: directly supplied by an external source.
- CALCULATED: deterministic computation from observed data.
- INFERRED: model/agent interpretation.

An inference may not be promoted to observed fact without new evidence.

## IDs
All externally meaningful records use opaque UUIDs. Workflow artifacts additionally carry a trace_id and run_id. Evidence IDs are stable within a decision run.

## Time
Every time-sensitive record carries:
- occurred_at/source timestamp
- published_at when applicable
- received_at
- persisted_at

Never substitute received_at for source time in backtests.
