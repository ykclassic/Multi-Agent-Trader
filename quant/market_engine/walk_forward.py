"""No-lookahead walk-forward evaluation and historical condition stratification.

This is research tooling, not an execution simulator or trading system. Signals
are evaluated on the following candle's close-to-close return and pay explicit
turnover costs. Liquidity-shock labels are OHLCV proxies, never true depth data.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from statistics import fmean, median, pstdev
from typing import Callable, Literal, Sequence

from .engine import Candle
from .market_state import classify_market_state
from .sessions import ForexSessionCalendar

Position = Literal[-1, 0, 1]
Predictor = Callable[[Sequence[Candle]], int]
StrategyFitter = Callable[[Sequence[Candle]], Predictor]
ALGORITHM_VERSION = "walk-forward-v1"


@dataclass(frozen=True, slots=True)
class WalkForwardConfig:
    train_window_candles: int = 100
    test_window_candles: int = 50
    step_candles: int = 50
    min_folds: int = 3
    min_observations_per_condition: int = 10
    fee_bps: float = 5.0
    slippage_bps: float = 2.0
    condition_lookback: int = 24
    bull_bear_return_threshold: float = 0.05
    high_volatility_threshold: float = 0.80
    shock_return_multiple: float = 3.0
    shock_return_floor: float = 0.01
    shock_volume_multiple: float = 2.0

    def validate(self) -> None:
        if self.train_window_candles < 27 or self.test_window_candles < 1:
            raise ValueError("Training window must be >=27 and test window must be positive")
        if self.step_candles < self.test_window_candles:
            raise ValueError("step_candles must be >= test_window_candles to avoid overlapping out-of-sample returns")
        if self.min_folds < 1 or self.min_observations_per_condition < 1:
            raise ValueError("Minimum folds and condition observations must be positive")
        for name in ("fee_bps", "slippage_bps", "bull_bear_return_threshold",
                     "high_volatility_threshold", "shock_return_multiple",
                     "shock_return_floor", "shock_volume_multiple"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.condition_lookback < 3:
            raise ValueError("condition_lookback must be at least 3")


@dataclass(frozen=True, slots=True)
class FoldResult:
    fold_index: int
    train_start_at: str
    train_end_at: str
    test_start_at: str
    test_end_at: str
    train_candle_count: int
    test_observation_count: int
    metrics: dict[str, float]
    condition_metrics: dict[str, dict[str, float]]
    condition_counts: dict[str, int]
    skipped_data_gap_count: int


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    status: Literal["completed", "insufficient_data"]
    algorithm_version: str
    strategy_id: str
    run_hash: str
    data_start_at: str | None
    data_end_at: str | None
    candle_count: int
    config: dict
    summary: dict[str, float | int | str | list[str]]
    folds: tuple[FoldResult, ...]
    condition_metrics: dict[str, dict[str, float]]
    condition_counts: dict[str, int]
    coverage_gaps: tuple[str, ...]

    def as_row(self, *, workspace_id: str, asset_class: str, instrument_id: str | None,
               instrument_symbol: str, timeframe_seconds: int) -> dict:
        return {
            "workspace_id": workspace_id, "asset_class": asset_class,
            "instrument_id": instrument_id, "instrument_symbol": instrument_symbol,
            "timeframe_seconds": timeframe_seconds, "data_start_at": self.data_start_at,
            "data_end_at": self.data_end_at, "algorithm_version": self.algorithm_version,
            "strategy_id": self.strategy_id, "run_hash": self.run_hash, "status": self.status, "config": self.config,
            "summary": self.summary,
            "folds": [asdict(fold) for fold in self.folds],
            "condition_metrics": self.condition_metrics,
        }


def _metrics(returns: Sequence[float], positions: Sequence[int], costs: Sequence[float],
             timeframe_seconds: int, *, market_type: str) -> dict[str, float]:
    if not returns:
        return {"observations": 0.0, "total_return": 0.0, "annualized_sharpe": 0.0,
                "max_drawdown": 0.0, "hit_rate": 0.0, "turnover": 0.0,
                "cost_fraction": 0.0, "exposure_fraction": 0.0}
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in returns:
        equity *= max(0.0, 1.0 + value)
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak if peak else 1.0)
    deviation = pstdev(returns) if len(returns) > 1 else 0.0
    annualization_days = 365.0 if market_type == "crypto" else 252.0
    periods_per_year = (annualization_days * 24.0 * 3600.0) / timeframe_seconds
    sharpe = fmean(returns) / deviation * math.sqrt(periods_per_year) if deviation > 0 else 0.0
    active = [value for value, position in zip(returns, positions) if position != 0]
    return {
        "observations": float(len(returns)),
        "total_return": equity - 1.0,
        "annualized_sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "hit_rate": sum(value > 0 for value in active) / len(active) if active else 0.0,
        "turnover": sum(abs(right - left) for left, right in zip([0, *positions[:-1]], positions)),
        "cost_fraction": sum(costs),
        "exposure_fraction": sum(position != 0 for position in positions) / len(positions),
    }


def _condition_labels(candles: Sequence[Candle], index: int, *, timeframe_seconds: int,
                      config: WalkForwardConfig, market_type: str) -> tuple[str, ...]:
    start = max(0, index - config.condition_lookback + 1)
    window = candles[start:index + 1]
    if len(window) < config.condition_lookback:
        return ("insufficient_history",)
    closes = [c.close for c in window]
    returns = [right / left - 1.0 for left, right in zip(closes, closes[1:])]
    trend_return = closes[-1] / closes[0] - 1.0
    annualization_days = 365.0 if market_type == "crypto" else 252.0
    annualization = math.sqrt((annualization_days * 24.0 * 3600.0) / timeframe_seconds)
    volatility = pstdev(returns) * annualization if len(returns) > 1 else 0.0
    labels: list[str] = []
    if trend_return >= config.bull_bear_return_threshold:
        labels.append("bull")
    elif trend_return <= -config.bull_bear_return_threshold:
        labels.append("bear")
    if volatility >= config.high_volatility_threshold:
        labels.append("high_volatility")
    prior_abs_returns = [abs(value) for value in returns[:-1]]
    prior_volumes = [c.volume for c in window[:-1]]
    if prior_abs_returns and prior_volumes:
        median_abs_return = median(prior_abs_returns)
        median_volume = median(prior_volumes)
        latest_abs_return = abs(returns[-1])
        return_shock = latest_abs_return >= max(
            config.shock_return_floor, config.shock_return_multiple * median_abs_return
        )
        volume_shock = window[-1].volume >= max(1e-12, config.shock_volume_multiple * median_volume)
        if return_shock and volume_shock:
            labels.append("liquidity_shock_proxy")
    return tuple(labels or ("other",))


def make_ema_regime_strategy(*, timeframe_seconds: int, market_type: str,
                             forex_calendar: ForexSessionCalendar | None = None,
                             min_quality_score: float = 0.70) -> StrategyFitter:
    """Create a simple, deterministic baseline fitter for research comparisons.

    This is not a production strategy. It emits long/short/flat from a
    quality-gated EMA regime and returns flat when history is not trustworthy.
    """
    if market_type not in ("crypto", "forex"):
        raise ValueError("market_type must be crypto or forex")
    def fit(_training: Sequence[Candle]) -> Predictor:
        def predict(history: Sequence[Candle]) -> int:
            if len(history) < 27:
                return 0
            state = classify_market_state(
                history, source="walk_forward_baseline", as_of=history[-1].timestamp,
                timeframe_seconds=timeframe_seconds, max_age_seconds=0,
                market_type=market_type, min_quality_score=min_quality_score,
                forex_calendar=forex_calendar,
            )
            if state.status != "ready":
                return 0
            return 1 if state.trend == "trend_up" else -1 if state.trend == "trend_down" else 0
        return predict
    return fit


def walk_forward_evaluate(candles: Sequence[Candle], *, timeframe_seconds: int,
                          fit_strategy: StrategyFitter,
                          config: WalkForwardConfig = WalkForwardConfig(),
                          market_type: str = "crypto",
                          forex_calendar: ForexSessionCalendar | None = None,
                          strategy_id: str = "custom") -> WalkForwardResult:
    """Fit only on each training window and evaluate on disjoint future returns.

    Predictor input ends at the decision candle. The scored return is the next
    candle's close-to-close return. Crypto gaps are excluded; forex closures are
    recognized using the session calendar. No order is created or simulated.
    """
    config.validate()
    if timeframe_seconds <= 0:
        raise ValueError("timeframe_seconds must be positive")
    if market_type not in ("crypto", "forex"):
        raise ValueError("market_type must be crypto or forex")
    if not strategy_id.strip() or len(strategy_id) > 100:
        raise ValueError("strategy_id must contain 1-100 characters")
    for candle in candles:
        candle.validate()
    timestamps = [c.timestamp.astimezone(timezone.utc) for c in candles]
    if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
        raise ValueError("Candles must be strictly ordered with no duplicates")
    calendar = forex_calendar or ForexSessionCalendar()
    fee_rate = (config.fee_bps + config.slippage_bps) / 10_000.0
    fold_results: list[FoldResult] = []
    all_returns: list[float] = []
    all_positions: list[int] = []
    all_costs: list[float] = []
    all_conditions: dict[str, list[float]] = {}
    all_condition_positions: dict[str, list[int]] = {}
    all_condition_costs: dict[str, list[float]] = {}
    coverage_gaps: list[str] = []
    n = len(candles)
    fold_start = 0
    fold_index = 0
    while True:
        train_start = fold_start
        train_end = train_start + config.train_window_candles
        test_start = train_end
        test_end = test_start + config.test_window_candles
        if test_end >= n:
            break
        training = tuple(candles[train_start:train_end])
        predictor = fit_strategy(training)
        fold_returns: list[float] = []
        fold_positions: list[int] = []
        fold_costs: list[float] = []
        condition_returns: dict[str, list[float]] = {}
        condition_positions: dict[str, list[int]] = {}
        condition_costs: dict[str, list[float]] = {}
        previous_position = 0
        skipped_gaps = 0
        for index in range(test_start, test_end):
            left, right = timestamps[index], timestamps[index + 1]
            if market_type == "crypto":
                valid_gap = abs((right - left).total_seconds() - timeframe_seconds) <= 1
            else:
                expected_open_seconds = calendar.trading_seconds_between(left + timedelta(seconds=timeframe_seconds), right)
                valid_gap = expected_open_seconds <= 1
            if not valid_gap:
                skipped_gaps += 1
                previous_position = 0
                continue
            history = tuple(candles[train_start:index + 1])
            signal = predictor(history)
            if isinstance(signal, bool) or signal not in (-1, 0, 1):
                raise ValueError("Strategy predictor must return -1, 0, or 1")
            gross_return = signal * (candles[index + 1].close / candles[index].close - 1.0)
            turnover = abs(signal - previous_position)
            cost = turnover * fee_rate
            net_return = gross_return - cost
            fold_returns.append(net_return)
            fold_positions.append(signal)
            fold_costs.append(cost)
            for label in _condition_labels(candles, index, timeframe_seconds=timeframe_seconds, config=config, market_type=market_type):
                condition_returns.setdefault(label, []).append(net_return)
                condition_positions.setdefault(label, []).append(signal)
                condition_costs.setdefault(label, []).append(cost)
                all_conditions.setdefault(label, []).append(net_return)
                all_condition_positions.setdefault(label, []).append(signal)
                all_condition_costs.setdefault(label, []).append(cost)
            previous_position = signal
        fold_metrics = _metrics(fold_returns, fold_positions, fold_costs, timeframe_seconds, market_type=market_type)
        fold_condition_metrics = {
            label: _metrics(values, condition_positions[label], condition_costs[label], timeframe_seconds, market_type=market_type)
            for label, values in condition_returns.items()
        }
        fold_results.append(FoldResult(
            fold_index=fold_index,
            train_start_at=timestamps[train_start].isoformat(),
            train_end_at=timestamps[train_end - 1].isoformat(),
            test_start_at=timestamps[test_start].isoformat(),
            test_end_at=timestamps[test_end].isoformat(),
            train_candle_count=len(training), test_observation_count=len(fold_returns),
            metrics=fold_metrics, condition_metrics=fold_condition_metrics,
            condition_counts={key: len(value) for key, value in condition_returns.items()},
            skipped_data_gap_count=skipped_gaps,
        ))
        all_returns.extend(fold_returns)
        all_positions.extend(fold_positions)
        all_costs.extend(fold_costs)
        fold_index += 1
        fold_start += config.step_candles
    condition_metrics = {
        label: _metrics(values, [0] * len(values), [0.0] * len(values), timeframe_seconds)
        for label, values in all_conditions.items()
    }
    condition_counts = {label: len(values) for label, values in all_conditions.items()}
    required = ("bull", "bear", "high_volatility", "liquidity_shock_proxy")
    for label in required:
        if condition_counts.get(label, 0) < config.min_observations_per_condition:
            coverage_gaps.append(f"{label}:requires_{config.min_observations_per_condition}_observations")
    if len(fold_results) < config.min_folds:
        coverage_gaps.append(f"walk_forward_folds:requires_{config.min_folds}_got_{len(fold_results)}")
    if not all_returns:
        coverage_gaps.append("no_valid_out_of_sample_returns")
    metrics = _metrics(all_returns, all_positions, all_costs, timeframe_seconds, market_type=market_type)
    metrics["fold_count"] = float(len(fold_results))
    metrics["skipped_data_gap_count"] = float(sum(fold.skipped_data_gap_count for fold in fold_results))
    metrics["condition_coverage_count"] = float(sum(condition_counts.get(label, 0) >= config.min_observations_per_condition for label in required))
    status: Literal["completed", "insufficient_data"] = "completed" if not coverage_gaps else "insufficient_data"
    fingerprint = {
        "algorithm_version": ALGORITHM_VERSION, "strategy_id": strategy_id,
        "config": asdict(config), "timeframe_seconds": timeframe_seconds, "market_type": market_type,
        "candles": [[ts.isoformat(), c.open, c.high, c.low, c.close, c.volume]
                    for ts, c in zip(timestamps, candles)],
    }
    run_hash = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    summary: dict[str, float | int | str | list[str]] = {
        **metrics, "status": status, "coverage_gaps": coverage_gaps,
        "fee_bps": config.fee_bps, "slippage_bps": config.slippage_bps,
        "liquidity_shock_label_type": "OHLCV_proxy_not_orderbook_liquidity",
    }
    return WalkForwardResult(
        status=status, algorithm_version=ALGORITHM_VERSION, strategy_id=strategy_id,
        run_hash=run_hash, data_start_at=timestamps[0].isoformat() if timestamps else None,
        data_end_at=timestamps[-1].isoformat() if timestamps else None,
        candle_count=n, config=asdict(config), summary=summary,
        folds=tuple(fold_results), condition_metrics=condition_metrics,
        condition_counts=condition_counts, coverage_gaps=tuple(coverage_gaps),
    )
