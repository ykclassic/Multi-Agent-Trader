"""Compare risk-limit candidates against immutable historical portfolio snapshots.

This is sensitivity analysis only: no candidate is selected or applied
automatically, and no order execution path exists.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
import sys

from quant.market_engine.calibration import RiskCalibrationCandidate, calibrate_risk_limits
from quant.market_engine.research_persistence import SupabaseRestResearchRepository
from quant.market_engine.risk import RiskLimits


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamps must include a timezone, e.g. 2026-01-01T00:00:00Z")
    return parsed.astimezone(timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibrate risk-limit sensitivity against point-in-time snapshots.")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--start", type=parse_datetime, required=True)
    parser.add_argument("--end", type=parse_datetime, required=True)
    parser.add_argument("--portfolio-id", help="Optional portfolio UUID to narrow the history")
    parser.add_argument("--min-samples", type=int, default=50)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.start >= args.end or args.min_samples < 1:
        print("start must precede end and min-samples must be positive", file=sys.stderr)
        return 2
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required in a trusted server environment", file=sys.stderr)
        return 2
    candidates = (
        RiskCalibrationCandidate("conservative", RiskLimits(
            max_daily_loss_fraction=0.01, max_drawdown_fraction=0.05,
            max_gross_exposure_fraction=0.75, max_net_exposure_fraction=0.50,
            max_single_position_fraction=0.15, max_open_risk_fraction=0.01,
            max_risk_per_trade_fraction=0.0025, max_positions=3,
            min_market_quality_score=0.80, max_market_data_age_seconds=300,
        )),
        RiskCalibrationCandidate("baseline", RiskLimits()),
        RiskCalibrationCandidate("less_restrictive_research_only", RiskLimits(
            max_daily_loss_fraction=0.03, max_drawdown_fraction=0.15,
            max_gross_exposure_fraction=1.00, max_net_exposure_fraction=0.90,
            max_single_position_fraction=0.35, max_open_risk_fraction=0.03,
            max_risk_per_trade_fraction=0.0075, max_positions=8,
            min_market_quality_score=0.65, max_market_data_age_seconds=3600,
        )),
    )
    try:
        repository = SupabaseRestResearchRepository.from_env()
        snapshots = repository.fetch_portfolio_snapshots(
            workspace_id=args.workspace_id, start_at=args.start, end_at=args.end,
            portfolio_id=args.portfolio_id,
        )
        report = calibrate_risk_limits(snapshots, candidates=candidates, min_samples=args.min_samples)
        run_id = repository.append_risk_calibration_report(
            report, workspace_id=args.workspace_id, portfolio_id=args.portfolio_id,
        )
        print(json.dumps({
            "status": report.status, "persisted": True, "run_id": run_id,
            "run_hash": report.run_hash, "snapshot_count": report.snapshot_count,
            "sample_count": report.sample_count, "candidates": [
                {
                    "candidate_id": item.candidate_id, "status": item.status,
                    "sample_count": item.sample_count, "allowed_count": item.allowed_count,
                    "rejected_count": item.rejected_count, "rejection_rate": item.rejection_rate,
                    "reason_counts": item.reason_counts, "limits": item.limits,
                } for item in report.candidates
            ], "coverage_gaps": list(report.coverage_gaps),
            "policy_changed": False,
        }, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)[:240]}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
