"""Deterministic market-state classification guarded by candle quality."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Sequence
from .engine import Candle, MarketSnapshot, build_market_snapshot
from .quality import MarketDataQuality, score_candle_batch
from .sessions import ForexSessionCalendar

TrendState = Literal["trend_up", "trend_down", "range", "unknown"]
VolatilityState = Literal["low", "normal", "high", "extreme", "unknown"]
MomentumState = Literal["oversold", "neutral", "overbought", "unknown"]

@dataclass(frozen=True, slots=True)
class MarketState:
    status: Literal["ready", "blocked"]
    trend: TrendState
    volatility: VolatilityState
    momentum: MomentumState
    quality_score: float
    latest_candle_at: str | None
    candle_count: int
    snapshot: MarketSnapshot | None
    quality: MarketDataQuality | None
    reasons: tuple[str, ...]
    evidence: tuple[str, ...]

def classify_market_state(candles: Sequence[Candle], *, source: str, as_of,
                          timeframe_seconds: int, market_type: str = "crypto",
                          max_age_seconds: int | None = None,
                          min_quality_score: float = 0.70,
                          forex_calendar: ForexSessionCalendar | None = None) -> MarketState:
    """Classify trend/volatility/momentum only when input passes quality gates.

    Volatility bands use annualized realized volatility: below 20% low, 20–60%
    normal, 60–100% high, above 100% extreme. They are broad defaults, not
    universal financial thresholds.
    """
    if not 0.0 <= min_quality_score <= 1.0:
        raise ValueError("min_quality_score must be between 0 and 1")
    if timeframe_seconds <= 0:
        raise ValueError("timeframe_seconds must be positive")
    age_limit = max_age_seconds if max_age_seconds is not None else max(2 * timeframe_seconds, 180)
    if age_limit < 0:
        raise ValueError("max_age_seconds cannot be negative")
    if not candles:
        return MarketState("blocked", "unknown", "unknown", "unknown", 0.0, None, 0,
                           None, None, ("empty_candle_batch",), ())
    quality = score_candle_batch(candles, source=source, as_of=as_of,
        timeframe_seconds=timeframe_seconds, max_age_seconds=age_limit,
        market_type=market_type, forex_calendar=forex_calendar)
    reasons: list[str] = []
    if len(candles) < 27:
        reasons.append("insufficient_candles:minimum_27")
    if quality.is_stale:
        reasons.append("stale_market_data")
    if quality.overall_quality_score < min_quality_score:
        reasons.append("market_data_quality_below_threshold")
    if quality.missing_candle_count:
        reasons.append("missing_expected_candles")
    if reasons:
        return MarketState("blocked", "unknown", "unknown", "unknown",
            quality.overall_quality_score, candles[-1].timestamp.isoformat(),
            len(candles), None, quality, tuple(reasons), tuple(quality.issues))
    snapshot = build_market_snapshot(candles, as_of=as_of,
        timeframe_seconds=timeframe_seconds, max_age_seconds=age_limit)
    vol = snapshot.realized_volatility_annualized
    volatility = "low" if vol < 0.20 else "normal" if vol < 0.60 else "high" if vol < 1.00 else "extreme"
    momentum = "oversold" if snapshot.rsi_14 < 30 else "overbought" if snapshot.rsi_14 > 70 else "neutral"
    evidence = (f"trend:{snapshot.regime}", f"rsi_14:{snapshot.rsi_14:.2f}",
        f"annualized_realized_volatility:{vol:.4f}", f"quality:{quality.overall_quality_score:.3f}")
    return MarketState("ready", snapshot.regime, volatility, momentum,
        quality.overall_quality_score, snapshot.latest_candle_at.isoformat(),
        len(candles), snapshot, quality, (), evidence)
