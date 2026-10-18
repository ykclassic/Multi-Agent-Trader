"""Persist one validated point-in-time portfolio snapshot from a trusted environment.

Example:
  python -m scripts.persist_portfolio_snapshot --input portfolio_snapshot.json

The input file must contain a PortfolioStateSnapshot mapping. Never place the
Supabase service-role key in that file or in client-side application code.
"""
from __future__ import annotations
import argparse
import json
import sys

from quant.market_engine.portfolio_state import PortfolioStateSnapshot
from quant.market_engine.research_persistence import SupabaseRestResearchRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist an immutable portfolio state snapshot.")
    parser.add_argument("--input", required=True, help="Path to a JSON snapshot document")
    args = parser.parse_args()
    try:
        with open(args.input, "r", encoding="utf-8") as stream:
            payload = json.load(stream)
        snapshot = PortfolioStateSnapshot.from_mapping(payload)
        repository = SupabaseRestResearchRepository.from_env()
        snapshot_id = repository.append_portfolio_snapshot(snapshot)
        print(json.dumps({
            "status": "persisted", "snapshot_id": snapshot_id,
            "portfolio_id": snapshot.portfolio_id, "as_of": snapshot.as_of.isoformat(),
            "state_hash": snapshot.state_hash,
        }, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)[:240]}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
