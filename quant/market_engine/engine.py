"""Pure deterministic OHLCV features and pre-trade position risk checks.

This module deliberately has no network, database, broker, or LLM dependencies.
It consumes validated candles and produces reproducible snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from statistics import fmean, pstdev
from typing import Literal, Sequence


@dataclass(frozen=True, slots=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def validate(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("Candle timestamp must be timezone-aware")
        values = (self.open, self.high, self.low, self.close, self.volume)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("OHLCV values must be finite numbers")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC prices must be greater than zero")
        if self.volume < 0:
            raise ValueError("Volume cannot be negative")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("High must be at least the open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("Low must be at most the open, close, and high")


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    as_of: datetime
    latest_candle_at: datetime
    age_seconds: float
    close: float
    return_1: float
    return_24: float
    ema_fast: float
    ema_slow: float
    rsi_14: float
    atr_14: float
    realized_volatility_annualized: float
    regime: Literal["trend_up", "trend_down", "range"]
    candle_count: int


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    allowed: bool
    reason: str
    quantity: float = 0.0
    notional: float = 0.0
    estimated_loss_at_stop: float = 0.0
    risk_fraction_of_equity: float = 0.0


def _ema(values: Sequence[float], period: int) -> float:
    if len(values) < period:
        raise ValueError(f"At least {period} observations are required for EMA")
    alpha = 2.0 / (period + 1.0)
    result = fmean(values[:period])
    for value in values[period:]:
        result = alpha * value + (1.0 - alpha) * result
    return result


def _rsi(closes: Sequence[float], period: int = 14) -> float:
    changes = [right - left for left, right in zip(closes, closes[1:])]
    if len(changes) < period:
        raise ValueError(f"At least {period + 1} closes are required for RSI")
    gains = [max(change, 0.0) for change in changes[-period:]]
    losses = [max(-change, 0.0) for change in changes[-period:]]
    average_gain, average_loss = fmean(gains), fmean(losses)
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def _atr(candles: Sequence[Candle], period: int = 14) -> float:
    true_ranges: list[float] = []
    for index, candle in enumerate(candles):
        previous_close = candles[index - 1].close if index else candle.close
        true_ranges.append(max(
            candle.high - candle.low,
            abs(candle.high - previous_close),
            abs(candle.low - previous_close),
        ))
    if len(true_ranges) < period:
        raise ValueError(f"At least {period} candles are required for ATR")
    return fmean(true_ranges[-period:])


def build_market_snapshot(
    candles: Sequence[Candle],
    *,
    as_of: datetime | None = None,
    timeframe_seconds: int = 3600,
    max_age_seconds: int = 180,
) -> MarketSnapshot:
    """Build features only from ordered, fresh, closed-candle input.

    The caller is responsible for ensuring the last candle is closed. This
    function rejects future-dated and stale data instead of silently using it.
    """
    if timeframe_seconds <= 0 or max_age_seconds < 0:
        raise ValueError("Timeframe must be positive and max age cannot be negative")
    if len(candles) < 27:
        raise ValueError("At least 27 candles are required to calculate the full snapshot")
    for candle in candles:
        candle.validate()
    times = [c.timestamp.astimezone(timezone.utc) for c in candles]
    if any(current <= previous for previous, current in zip(times, times[1:])):
        raise ValueError("Candles must be strictly ordered by timestamp with no duplicates")
    current_time = (as_of or datetime.now(timezone.utc))
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    current_time = current_time.astimezone(timezone.utc)
    latest_at = times[-1]
    age = (current_time - latest_at).total_seconds()
    if age < 0:
        raise ValueError("Latest candle is future-dated")
    if age > max_age_seconds:
        raise ValueError(f"Market data is stale: age {age:.0f}s exceeds {max_age_seconds}s")

    closes = [c.close for c in candles]
    returns = [right / left - 1.0 for left, right in zip(closes, closes[1:])]
    recent_returns = returns[-24:]
    annualization_factor = math.sqrt((365.0 * 24.0 * 3600.0) / timeframe_seconds)
    volatility = pstdev(recent_returns) * annualization_factor if len(recent_returns) > 1 else 0.0
    fast, slow = _ema(closes, 12), _ema(closes, 26)
    regime: Literal["trend_up", "trend_down", "range"]
    if fast > slow * 1.001:
        regime = "trend_up"
    elif fast < slow * 0.999:
        regime = "trend_down"
    else:
        regime = "range"

    return MarketSnapshot(
        as_of=current_time,
        latest_candle_at=latest_at,
        age_seconds=age,
        close=closes[-1],
        return_1=returns[-1],
        return_24=closes[-1] / closes[-25] - 1.0,
        ema_fast=fast,
        ema_slow=slow,
        rsi_14=_rsi(closes),
        atr_14=_atr(candles),
        realized_volatility_annualized=volatility,
        regime=regime,
        candle_count=len(candles),
    )


def assess_position_risk(
    *,
    equity: float,
    entry_price: float,
    stop_price: float,
    side: Literal["long", "short"],
    risk_fraction: float = 0.005,
    max_notional_fraction: float = 1.0,
) -> RiskAssessment:
    """Size a position under both stop-loss risk and gross-notional limits."""
    numbers = (equity, entry_price, stop_price, risk_fraction, max_notional_fraction)
    if not all(math.isfinite(value) for value in numbers):
        return RiskAssessment(False, "All inputs must be finite numbers")
    if equity <= 0 or entry_price <= 0 or stop_price <= 0:
        return RiskAssessment(False, "Equity and prices must be greater than zero")
    if not 0 < risk_fraction <= 0.02:
        return RiskAssessment(False, "Risk fraction must be greater than 0 and at most 2%")
    if not 0 < max_notional_fraction <= 1.0:
        return RiskAssessment(False, "Max notional fraction must be greater than 0 and at most 100%")
    if side not in ("long", "short"):
        return RiskAssessment(False, "Side must be long or short")
    if (side == "long" and stop_price >= entry_price) or (side == "short" and stop_price <= entry_price):
        return RiskAssessment(False, "Stop must be below entry for long and above entry for short")

    per_unit_risk = abs(entry_price - stop_price)
    risk_budget = equity * risk_fraction
    risk_limited_quantity = risk_budget / per_unit_risk
    notional_limited_quantity = (equity * max_notional_fraction) / entry_price
    quantity = min(risk_limited_quantity, notional_limited_quantity)
    notional = quantity * entry_price
    estimated_loss = quantity * per_unit_risk
    return RiskAssessment(
        allowed=quantity > 0,
        reason="Position is within configured risk and notional limits",
        quantity=quantity,
        notional=notional,
        estimated_loss_at_stop=estimated_loss,
        risk_fraction_of_equity=estimated_loss / equity,
    )
