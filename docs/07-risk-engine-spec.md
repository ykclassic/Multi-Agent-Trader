# Risk Engine Specification

## Deterministic responsibilities
- trade risk
- stop distance
- position sizing
- leverage
- gross/net exposure
- margin utilization
- portfolio concentration
- correlation/factor exposure
- volatility
- liquidity and estimated slippage
- drawdown
- daily/weekly loss limits
- strategy-specific risk budgets

## Hard limits
Examples:
- max risk per trade
- max gross exposure
- max net exposure
- max leverage
- max portfolio drawdown
- max daily loss
- max spread
- max estimated slippage
- max stale-data age
- max position concentration

Values are strategy/workspace configuration, not LLM output.

## Result
```text
RiskAssessment
  status: PASS | REDUCE | REJECT
  calculated_size
  max_size
  expected_slippage
  portfolio_exposure
  leverage
  drawdown_state
  violated_rules[]
  warnings[]
```

## Principle
The Trader may propose risk intent; the Quant Risk Engine computes the actual permitted size. The LLM cannot override a hard rule.
