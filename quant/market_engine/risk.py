"""Pure portfolio risk-policy checks; disconnected from order execution."""
from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_daily_loss_fraction: float = 0.02
    max_drawdown_fraction: float = 0.10
    max_gross_exposure_fraction: float = 1.00
    max_net_exposure_fraction: float = 0.75
    max_single_position_fraction: float = 0.25
    max_open_risk_fraction: float = 0.02
    max_risk_per_trade_fraction: float = 0.005
    max_positions: int = 5
    min_market_quality_score: float = 0.70
    max_market_data_age_seconds: float = 600.0

    def validate(self) -> None:
        fractions = (self.max_daily_loss_fraction, self.max_drawdown_fraction,
            self.max_gross_exposure_fraction, self.max_net_exposure_fraction,
            self.max_single_position_fraction, self.max_open_risk_fraction,
            self.max_risk_per_trade_fraction, self.min_market_quality_score)
        if not all(math.isfinite(x) and 0 <= x <= 1 for x in fractions):
            raise ValueError("Risk limit fractions must be finite values between 0 and 1")
        if self.max_positions < 0:
            raise ValueError("max_positions cannot be negative")
        if not math.isfinite(self.max_market_data_age_seconds) or self.max_market_data_age_seconds < 0:
            raise ValueError("max_market_data_age_seconds must be finite and non-negative")

@dataclass(frozen=True, slots=True)
class PortfolioRiskState:
    equity: float
    daily_pnl: float
    peak_equity: float
    gross_notional: float
    net_notional: float
    open_risk: float
    open_positions: int
    largest_position_notional: float

@dataclass(frozen=True, slots=True)
class ProposedExposure:
    notional: float
    estimated_loss_at_stop: float
    market_quality_score: float
    market_data_age_seconds: float
    market_data_valid: bool = True

@dataclass(frozen=True, slots=True)
class RiskPolicyDecision:
    allowed: bool
    reasons: tuple[str, ...]
    daily_loss_fraction: float
    drawdown_fraction: float
    projected_gross_exposure_fraction: float
    projected_net_exposure_fraction: float
    projected_open_risk_fraction: float
    projected_single_position_fraction: float

def evaluate_portfolio_risk(portfolio: PortfolioRiskState, proposed: ProposedExposure, *,
                            limits: RiskLimits = RiskLimits(),
                            signed_notional: float | None = None) -> RiskPolicyDecision:
    """Evaluate exposure against hard limits; this function never places an order.

    signed_notional is positive for long and negative for short exposure. If
    omitted, proposed exposure is treated as long. Invalid inputs fail closed.
    """
    limits.validate()
    signed_value = proposed.notional if signed_notional is None else signed_notional
    numeric = (portfolio.equity, portfolio.daily_pnl, portfolio.peak_equity,
        portfolio.gross_notional, portfolio.net_notional, portfolio.open_risk,
        portfolio.largest_position_notional, proposed.notional,
        proposed.estimated_loss_at_stop, proposed.market_quality_score,
        proposed.market_data_age_seconds, signed_value)
    reasons: list[str] = []
    if not all(math.isfinite(value) for value in numeric):
        reasons.append("non_finite_risk_input")
    if portfolio.equity <= 0 or portfolio.peak_equity <= 0:
        reasons.append("invalid_equity")
    elif portfolio.peak_equity < portfolio.equity:
        reasons.append("peak_equity_below_current_equity")
    if min(portfolio.gross_notional, portfolio.open_risk, portfolio.largest_position_notional,
           proposed.notional, proposed.estimated_loss_at_stop) < 0:
        reasons.append("negative_exposure_or_risk")
    if portfolio.open_positions < 0:
        reasons.append("invalid_open_position_count")
    if proposed.market_data_valid is not True:
        reasons.append("market_data_invalid")
    if not 0.0 <= proposed.market_quality_score <= 1.0:
        reasons.append("invalid_market_data_quality_score")
    if abs(signed_value) > proposed.notional:
        reasons.append("signed_notional_exceeds_proposed_notional")
    if proposed.market_quality_score < limits.min_market_quality_score:
        reasons.append("market_data_quality_below_minimum")
    if proposed.market_data_age_seconds < 0 or proposed.market_data_age_seconds > limits.max_market_data_age_seconds:
        reasons.append("market_data_stale_or_future_dated")
    safe_equity = portfolio.equity if math.isfinite(portfolio.equity) and portfolio.equity > 0 else 1.0
    daily_loss = max(0.0, -portfolio.daily_pnl / safe_equity)
    drawdown = max(0.0, (portfolio.peak_equity - portfolio.equity) / portfolio.peak_equity) if portfolio.peak_equity > 0 else 1.0
    signed = signed_value
    gross = (portfolio.gross_notional + proposed.notional) / safe_equity
    net = abs(portfolio.net_notional + signed) / safe_equity
    open_risk = (portfolio.open_risk + proposed.estimated_loss_at_stop) / safe_equity
    single = max(portfolio.largest_position_notional, proposed.notional) / safe_equity
    if daily_loss >= limits.max_daily_loss_fraction: reasons.append("daily_loss_limit_reached")
    if drawdown >= limits.max_drawdown_fraction: reasons.append("drawdown_limit_reached")
    if gross > limits.max_gross_exposure_fraction: reasons.append("gross_exposure_limit_exceeded")
    if net > limits.max_net_exposure_fraction: reasons.append("net_exposure_limit_exceeded")
    if open_risk > limits.max_open_risk_fraction: reasons.append("open_risk_limit_exceeded")
    if proposed.estimated_loss_at_stop / safe_equity > limits.max_risk_per_trade_fraction:
        reasons.append("per_trade_risk_limit_exceeded")
    if single > limits.max_single_position_fraction: reasons.append("single_position_concentration_limit_exceeded")
    if portfolio.open_positions >= limits.max_positions: reasons.append("maximum_open_positions_reached")
    return RiskPolicyDecision(not reasons, tuple(dict.fromkeys(reasons)), daily_loss, drawdown,
        gross, net, open_risk, single)
