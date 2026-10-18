"""Run a reproducible, point-in-time crypto/forex walk-forward research job.

This command only reads candle revisions and writes research metrics. It has no
broker or order-execution path.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
import sys

from quant.market_engine.research_persistence import SupabaseRestResearchRepository
from quant.market_engine.sessions import load_forex_session_calendar
from quant.market_engine.walk_forward import WalkForwardConfig, make_ema_regime_strategy, walk_forward_evaluate


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamps must include a timezone, e.g. 2025-01-01T00:00:00Z")
    return parsed.astimezone(timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run historical walk-forward evaluation without execution.")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--instrument-id", required=True, help="UUID from the active instrument registry")
    parser.add_argument("--symbol", required=True, help="Canonical registered symbol, e.g. BTC/USDT or EUR/USD")
    parser.add_argument("--asset-class", choices=("crypto", "forex"), required=True)
    parser.add_argument("--timeframe-seconds", type=int, required=True)
    parser.add_argument("--start", type=parse_datetime, required=True)
    parser.add_argument("--end", type=parse_datetime, required=True)
    parser.add_argument("--max-observation-delay-seconds", type=int, default=300)
    parser.add_argument("--train-window-candles", type=int, default=100)
    parser.add_argument("--test-window-candles", type=int, default=50)
    parser.add_argument("--step-candles", type=int, default=50)
    parser.add_argument("--min-folds", type=int, default=3)
    parser.add_argument("--min-observations-per-condition", type=int, default=10)
    parser.add_argument("--fee-bps", type=float, default=5.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--condition-lookback", type=int, default=24)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.start >= args.end or args.timeframe_seconds <= 0:
        print("start must precede end and timeframe-seconds must be positive", file=sys.stderr)
        return 2
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required in a trusted server environment", file=sys.stderr)
        return 2
    try:
        repository = SupabaseRestResearchRepository.from_env()
        point_in_time = repository.fetch_point_in_time_candles(
            instrument_id=args.instrument_id, timeframe_seconds=args.timeframe_seconds,
            start_at=args.start, end_at=args.end,
            max_observation_delay_seconds=args.max_observation_delay_seconds,
        )
        candles = tuple(item.candle for item in point_in_time)
        config = WalkForwardConfig(
            train_window_candles=args.train_window_candles,
            test_window_candles=args.test_window_candles, step_candles=args.step_candles,
            min_folds=args.min_folds,
            min_observations_per_condition=args.min_observations_per_condition,
            fee_bps=args.fee_bps, slippage_bps=args.slippage_bps,
            condition_lookback=args.condition_lookback,
        )
        calendar = load_forex_session_calendar(require_confirmed=True) if args.asset_class == "forex" else None
        result = walk_forward_evaluate(
            candles, timeframe_seconds=args.timeframe_seconds,
            fit_strategy=make_ema_regime_strategy(
                timeframe_seconds=args.timeframe_seconds, market_type=args.asset_class,
                forex_calendar=calendar,
            ),
            config=config, market_type=args.asset_class, forex_calendar=calendar,
        )
        if len(candles) < 2:
            print(json.dumps({
                "status": "insufficient_data", "persisted": False,
                "reason": "at least two point-in-time candles are required to persist a dated research run",
                "candle_count": len(candles), "run_hash": result.run_hash,
            }, indent=2))
            return 0
        run_id = repository.append_walk_forward_result(
            result, workspace_id=args.workspace_id, asset_class=args.asset_class,
            instrument_id=args.instrument_id, instrument_symbol=args.symbol,
            timeframe_seconds=args.timeframe_seconds,
        )
        print(json.dumps({
            "status": result.status, "persisted": True, "run_id": run_id,
            "run_hash": result.run_hash, "point_in_time_candles": len(point_in_time),
            "distinct_revision_hashes": len({item.content_hash for item in point_in_time}),
            "summary": result.summary, "condition_counts": result.condition_counts,
            "coverage_gaps": list(result.coverage_gaps),
        }, indent=2))
        # An insufficient-data report is a valid research artifact, not a successful calibration.
        return 0 if result.status in ("completed", "insufficient_data") else 1
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)[:240]}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
