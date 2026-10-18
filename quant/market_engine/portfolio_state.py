"""Validated immutable portfolio state snapshots for point-in-time risk research."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Literal, Sequence

from .risk import (
    PortfolioRiskState, ProposedExposure, RiskLimits, RiskPolicyDecision, evaluate_portfolio_risk,
)

SnapshotSource = Literal["manual_import", "historical_replay", "read_only_import"]
AssetClass = Literal["crypto", "forex"]
PositionSide = Literal["long", "short"]


def _aware_utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _finite(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    symbol: str
    asset_class: AssetClass
    side: PositionSide
    quantity: float
    mark_price: float
    notional: float
    estimated_loss_at_stop: float

    def validate(self) -> None:
        if not self.symbol.strip() or len(self.symbol) > 80:
            raise ValueError("Position symbol must contain 1-80 characters")
        if self.asset_class not in ("crypto", "forex"):
            raise ValueError("Position asset_class must be crypto or forex")
        if self.side not in ("long", "short"):
            raise ValueError("Position side must be long or short")
        for name in ("quantity", "mark_price", "notional"):
            if _finite(getattr(self, name), name) <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if _finite(self.estimated_loss_at_stop, "estimated_loss_at_stop") < 0:
            raise ValueError("estimated_loss_at_stop cannot be negative")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "symbol": self.symbol, "asset_class": self.asset_class, "side": self.side,
            "quantity": float(self.quantity), "mark_price": float(self.mark_price),
            "notional": float(self.notional),
            "estimated_loss_at_stop": float(self.estimated_loss_at_stop),
        }


@dataclass(frozen=True, slots=True)
class PortfolioStateSnapshot:
    portfolio_id: str
    workspace_id: str
    as_of: datetime
    market_data_as_of: datetime
    source: SnapshotSource
    base_currency: str
    cash_balance: float
    equity: float
    daily_pnl: float
    peak_equity: float
    market_data_quality_score: float
    positions: tuple[PositionSnapshot, ...]
    metadata: dict[str, Any] | None = None

    def validate(self) -> None:
        if not self.portfolio_id.strip() or not self.workspace_id.strip():
            raise ValueError("portfolio_id and workspace_id are required")
        if _aware_utc(self.market_data_as_of, "market_data_as_of") > _aware_utc(self.as_of, "as_of"):
            raise ValueError("market_data_as_of cannot be later than portfolio as_of")
        if self.source not in ("manual_import", "historical_replay", "read_only_import"):
            raise ValueError("Unsupported portfolio snapshot source")
        if not self.base_currency.isascii() or not self.base_currency.isupper() or not (3 <= len(self.base_currency) <= 8):
            raise ValueError("base_currency must be an uppercase 3-8 character code")
        cash = _finite(self.cash_balance, "cash_balance")
        equity = _finite(self.equity, "equity")
        pnl = _finite(self.daily_pnl, "daily_pnl")
        peak = _finite(self.peak_equity, "peak_equity")
        quality = _finite(self.market_data_quality_score, "market_data_quality_score")
        if equity <= 0 or peak < equity:
            raise ValueError("equity must be positive and peak_equity must be at least equity")
        if not 0 <= quality <= 1:
            raise ValueError("market_data_quality_score must be between 0 and 1")
        for position in self.positions:
            position.validate()
        gross = sum(p.notional for p in self.positions)
        net = sum(p.notional if p.side == "long" else -p.notional for p in self.positions)
        open_risk = sum(p.estimated_loss_at_stop for p in self.positions)
        largest = max((p.notional for p in self.positions), default=0.0)
        if not all(math.isfinite(x) for x in (gross, net, open_risk, largest, cash, pnl)):
            raise ValueError("Derived portfolio exposure values must be finite")
        if self.metadata is not None:
            try:
                json.dumps(self.metadata, allow_nan=False, sort_keys=True)
            except (TypeError, ValueError):
                raise ValueError("metadata must be JSON-serializable and finite") from None

    @property
    def gross_notional(self) -> float:
        return sum(p.notional for p in self.positions)

    @property
    def net_notional(self) -> float:
        return sum(p.notional if p.side == "long" else -p.notional for p in self.positions)

    @property
    def open_risk(self) -> float:
        return sum(p.estimated_loss_at_stop for p in self.positions)

    @property
    def open_positions(self) -> int:
        return len(self.positions)

    @property
    def largest_position_notional(self) -> float:
        return max((p.notional for p in self.positions), default=0.0)

    @property
    def state_hash(self) -> str:
        self.validate()
        canonical = {
            "portfolio_id": self.portfolio_id, "workspace_id": self.workspace_id,
            "as_of": _aware_utc(self.as_of, "as_of").isoformat(),
            "market_data_as_of": _aware_utc(self.market_data_as_of, "market_data_as_of").isoformat(),
            "source": self.source, "base_currency": self.base_currency,
            "cash_balance": float(self.cash_balance), "equity": float(self.equity),
            "daily_pnl": float(self.daily_pnl), "peak_equity": float(self.peak_equity),
            "market_data_quality_score": float(self.market_data_quality_score),
            "positions": [p.as_dict() for p in self.positions],
            "metadata": self.metadata or {},
        }
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return hashlib.sha256(encoded).hexdigest()

    def as_risk_state(self) -> PortfolioRiskState:
        self.validate()
        return PortfolioRiskState(
            equity=self.equity, daily_pnl=self.daily_pnl, peak_equity=self.peak_equity,
            gross_notional=self.gross_notional, net_notional=self.net_notional,
            open_risk=self.open_risk, open_positions=self.open_positions,
            largest_position_notional=self.largest_position_notional,
        )

    def as_row(self) -> dict[str, Any]:
        self.validate()
        return {
            "portfolio_id": self.portfolio_id, "workspace_id": self.workspace_id,
            "as_of": _aware_utc(self.as_of, "as_of").isoformat(),
            "source": self.source, "base_currency": self.base_currency,
            "cash_balance": self.cash_balance, "equity": self.equity,
            "daily_pnl": self.daily_pnl, "peak_equity": self.peak_equity,
            "gross_notional": self.gross_notional, "net_notional": self.net_notional,
            "open_risk": self.open_risk, "open_positions": self.open_positions,
            "largest_position_notional": self.largest_position_notional,
            "market_data_quality_score": self.market_data_quality_score,
            "market_data_as_of": _aware_utc(self.market_data_as_of, "market_data_as_of").isoformat(),
            "positions": [p.as_dict() for p in self.positions],
            "state_hash": self.state_hash, "metadata": self.metadata or {},
        }

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "PortfolioStateSnapshot":
        def parse_time(key: str) -> datetime:
            value = payload[key]
            parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return _aware_utc(parsed, key)
        positions = tuple(PositionSnapshot(
            symbol=str(item["symbol"]), asset_class=item["asset_class"], side=item["side"],
            quantity=float(item["quantity"]), mark_price=float(item["mark_price"]),
            notional=float(item["notional"]),
            estimated_loss_at_stop=float(item["estimated_loss_at_stop"]),
        ) for item in payload.get("positions", ()))
        snapshot = cls(
            portfolio_id=str(payload["portfolio_id"]), workspace_id=str(payload["workspace_id"]),
            as_of=parse_time("as_of"), market_data_as_of=parse_time("market_data_as_of"),
            source=payload["source"], base_currency=str(payload.get("base_currency", "USD")),
            cash_balance=float(payload["cash_balance"]), equity=float(payload["equity"]),
            daily_pnl=float(payload["daily_pnl"]), peak_equity=float(payload["peak_equity"]),
            market_data_quality_score=float(payload["market_data_quality_score"]),
            positions=positions, metadata=payload.get("metadata", {}),
        )
        snapshot.validate()
        return snapshot


def evaluate_snapshot_proposal(snapshot: PortfolioStateSnapshot, proposed: ProposedExposure, *,
                               limits: RiskLimits = RiskLimits(),
                               signed_notional: float | None = None) -> RiskPolicyDecision:
    """Apply the portfolio risk policy to a validated persisted point-in-time snapshot."""
    return evaluate_portfolio_risk(
        snapshot.as_risk_state(), proposed, limits=limits, signed_notional=signed_notional,
    )
