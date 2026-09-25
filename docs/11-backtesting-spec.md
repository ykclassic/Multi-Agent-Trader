# Backtesting Specification

## Event-driven replay
Backtests reconstruct the information available at each historical decision time.

```
historical event
 -> point-in-time state
 -> agent workflow
 -> trade proposal
 -> deterministic risk
 -> simulated execution
 -> portfolio update
 -> next event
```

## Must model
- bid/ask spread
- fees
- slippage
- latency
- partial fills
- liquidity/market impact
- crypto funding
- forex financing/swap where applicable
- venue outages when historical data permits

## Leakage controls
- no future news
- no revised macro value before revision/publication
- no future candles/features
- no future position information
- no post-event labels in prompts

## Validation
Use train/validation/test separation and walk-forward evaluation. Report regime-segmented metrics and confidence calibration.

## Ablations
At minimum compare:
- full system
- quant-only
- technical-only
- no debate
- no news
- no sentiment
- no macro
- no derivatives
- no on-chain

## Metrics
Return, volatility, drawdown, Sharpe/Sortino where appropriate, turnover, hit rate, profit factor, fees, slippage, exposure, tail losses and trade-level attribution.

Backtest results are research evidence, not a guarantee of future performance.
