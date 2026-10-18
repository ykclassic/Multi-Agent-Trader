"""Create a workspace-scoped research portfolio from a trusted server environment."""
from __future__ import annotations
import argparse
import json
import os
import sys

from quant.market_engine.research_persistence import SupabaseRestResearchRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a portfolio container for read-only risk research.")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--base-currency", default="USD")
    parser.add_argument("--created-by", help="Optional authenticated user UUID for audit metadata")
    args = parser.parse_args()
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required in a trusted server environment", file=sys.stderr)
        return 2
    try:
        repository = SupabaseRestResearchRepository.from_env()
        portfolio_id = repository.create_portfolio(
            workspace_id=args.workspace_id, name=args.name,
            base_currency=args.base_currency, created_by=args.created_by,
        )
        print(json.dumps({
            "status": "created_or_existing", "portfolio_id": portfolio_id,
            "workspace_id": args.workspace_id, "name": args.name.strip(),
            "base_currency": args.base_currency,
        }, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)[:240]}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
