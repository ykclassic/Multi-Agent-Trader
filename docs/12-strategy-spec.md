# Strategy Specification

A strategy is a versioned declarative contract.

## Required
```text
strategy_id
version
asset_classes
instruments/universe
timeframes
trigger policy
required data
enabled agents
entry/exit semantics
risk policy
execution policy
schedule/event triggers
```

## Examples of strategy families
- crypto trend
- crypto mean reversion
- crypto derivatives/funding
- FX macro
- FX breakout
- cross-asset portfolio

Names describe implementation families only; they are not claims of profitability.

## Strategy lifecycle
DRAFT -> BACKTESTED -> PAPER -> APPROVED -> LIVE -> SUSPENDED -> RETIRED

Only approved versions can reach Policy Gate.
