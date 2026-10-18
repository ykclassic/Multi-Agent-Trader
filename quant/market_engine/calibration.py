"""Historical sensitivity analysis for portfolio risk limits; never auto-promotes policy."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timezone
import hashlib
import json
from typing import Sequence

from .portfolio_state import PortfolioStateSnapshot
from .risk import PortfolioRiskState, ProposedExposure, RiskLimits, evaluate_portfolio_risk

CALIBRATION_VERSION = "risk-threshold-sensitivity-v1"


@dataclass(frozen=True, slots=True)
class RiskCalibrationCandidate:
    candidate_id: str
    limits: RiskLimits

    def validate(self) -> None:
        if not self.candidate_id.strip() or len(self.candidate_id) > 100:
            raise ValueError("candidate_id must contain 1-100 characters")
        self.limits.validate()


@dataclass(frozen=True, slots=True)
class RiskCalibrationCandidateResult:
    candidate_id: str
    limits: dict
    sample_count: int
    allowed_count: int
    rejected_count: int
    rejection_rate: float
    reason_counts: dict[str, int]
    status: str


@dataclass(frozen=True, slots=True)
class RiskCalibrationReport:
    status: str
    calibration_version: str
    run_hash: str
    snapshot_count: int
    sample_count: int
    data_start_at: str | None
    data_end_at: str | None
    min_samples_required: int
    candidates: tuple[RiskCalibrationCandidateResult, ...]
    coverage_gaps: tuple[str, ...]

    def as_row(self, *, workspace_id: str, portfolio_id: str | None) -> dict:
        return {
            "workspace_id": workspace_id, "portfolio_id": portfolio_id,
            "calibration_version": self.calibration_version, "run_hash": self.run_hash,
            "snapshot_count": self.snapshot_count, "sample_count": self.sample_count,
            "data_start_at": self.data_start_at, "data_end_at": self.data_end_at,
            "min_samples_required": self.min_samples_required, "status": self.status,
            "candidate_results": [asdict(item) for item in self.candidates],
            "coverage_gaps": list(self.coverage_gaps),
        }


def _position_scenarios(snapshot: PortfolioStateSnapshot):
    state = snapshot.as_risk_state()
    age = max(0.0, (snapshot.as_of.astimezone(timezone.utc)
                    - snapshot.market_data_as_of.astimezone(timezone.utc)).total_seconds())
    if not snapshot.positions:
        yield state, ProposedExposure(
            notional=0.0, estimated_loss_at_stop=0.0,
            market_quality_score=snapshot.market_data_quality_score,
            market_data_age_seconds=age, market_data_valid=True,
        ), 0.0
        return
    for position in snapshot.positions:
        signed = position.notional if position.side == "long" else -position.notional
        remaining_positions = [other for other in snapshot.positions if other is not position]
        base = PortfolioRiskState(
            equity=state.equity, daily_pnl=state.daily_pnl, peak_equity=state.peak_equity,
            gross_notional=max(0.0, state.gross_notional - position.notional),
            net_notional=state.net_notional - signed,
            open_risk=max(0.0, state.open_risk - position.estimated_loss_at_stop),
            open_positions=max(0, state.open_positions - 1),
            largest_position_notional=max((other.notional for other in remaining_positions), default=0.0),
        )
        proposed = ProposedExposure(
            notional=position.notional, estimated_loss_at_stop=position.estimated_loss_at_stop,
            market_quality_score=snapshot.market_data_quality_score,
            market_data_age_seconds=age, market_data_valid=True,
        )
        yield base, proposed, signed


def calibrate_risk_limits(snapshots: Sequence[PortfolioStateSnapshot], *,
                          candidates: Sequence[RiskCalibrationCandidate],
                          min_samples: int = 50) -> RiskCalibrationReport:
    """Compare policy candidates against observed snapshots and position exposures.

    This measures historical acceptance/rejection sensitivity, not expected
    profitability. A candidate is marked insufficient_data until the configured
    minimum number of position/snapshot scenarios exists. No candidate is
    selected or applied automatically.
    """
    if min_samples < 1:
        raise ValueError("min_samples must be positive")
    if not candidates:
        raise ValueError("At least one risk calibration candidate is required")
    if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
        raise ValueError("candidate_id values must be unique")
    for candidate in candidates:
        candidate.validate()
    for snapshot in snapshots:
        snapshot.validate()

    candidate_results: list[RiskCalibrationCandidateResult] = []
    sample_count = sum(1 for snapshot in snapshots for _ in _position_scenarios(snapshot))
    for candidate in candidates:
        allowed = rejected = 0
        reasons: dict[str, int] = {}
        count = 0
        for snapshot in snapshots:
            for state, proposed, signed in _position_scenarios(snapshot):
                decision = evaluate_portfolio_risk(
                    state, proposed, limits=candidate.limits, signed_notional=signed,
                )
                count += 1
                if decision.allowed:
                    allowed += 1
                else:
                    rejected += 1
                    for reason in decision.reasons:
                        reasons[reason] = reasons.get(reason, 0) + 1
        candidate_results.append(RiskCalibrationCandidateResult(
            candidate_id=candidate.candidate_id, limits=asdict(candidate.limits),
            sample_count=count, allowed_count=allowed, rejected_count=rejected,
            rejection_rate=rejected / count if count else 0.0,
            reason_counts=dict(sorted(reasons.items())),
            status="completed" if count >= min_samples else "insufficient_data",
        ))

    dates = sorted(snapshot.as_of.astimezone(timezone.utc) for snapshot in snapshots)
    gaps: list[str] = []
    if sample_count < min_samples:
        gaps.append(f"risk_scenarios:requires_{min_samples}_got_{sample_count}")
    if len(snapshots) < 2:
        gaps.append("portfolio_snapshot_history:requires_at_least_2_snapshots")
    fingerprint = {
        "version": CALIBRATION_VERSION, "min_samples": min_samples,
        "snapshot_hashes": sorted(snapshot.state_hash for snapshot in snapshots),
        "candidates": [{"candidate_id": item.candidate_id, "limits": asdict(item.limits)}
                       for item in candidates],
    }
    run_hash = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, separators=(",", ":"),
                                         allow_nan=False).encode()).hexdigest()
    return RiskCalibrationReport(
        status="completed" if not gaps else "insufficient_data",
        calibration_version=CALIBRATION_VERSION, run_hash=run_hash,
        snapshot_count=len(snapshots), sample_count=sample_count,
        data_start_at=dates[0].isoformat() if dates else None,
        data_end_at=dates[-1].isoformat() if dates else None,
        min_samples_required=min_samples, candidates=tuple(candidate_results),
        coverage_gaps=tuple(gaps),
    )
