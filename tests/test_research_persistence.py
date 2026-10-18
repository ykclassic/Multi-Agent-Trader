from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import unittest
from unittest.mock import patch

from quant.market_engine.engine import Candle
from quant.market_engine.portfolio_state import PortfolioStateSnapshot
from quant.market_engine.research_persistence import SupabaseRestResearchRepository


class FakeResponse:
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self.body).encode("utf-8")


def sample_snapshot():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return PortfolioStateSnapshot(
        portfolio_id="portfolio-1", workspace_id="workspace-1",
        as_of=now, market_data_as_of=now, source="manual_import",
        base_currency="USD", cash_balance=10000, equity=10000,
        daily_pnl=0, peak_equity=10000, market_data_quality_score=1.0,
        positions=(),
    )


class ResearchPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.repo = SupabaseRestResearchRepository(
            supabase_url="https://example.supabase.co", service_role_key="server-only-test-secret"
        )

    def test_point_in_time_candle_fetch_uses_rpc_and_validates_result(self):
        observed = datetime(2025, 1, 1, 1, 5, tzinfo=timezone.utc)
        body = [{
            "candle_at": "2025-01-01T01:00:00+00:00",
            "open": 100, "high": 102, "low": 99, "close": 101, "volume": 10,
            "observed_at": observed.isoformat(), "content_hash": "a" * 64, "quality_score": 0.95,
        }]
        with patch("quant.market_engine.research_persistence.urlopen", return_value=FakeResponse(body)) as urlopen:
            result = self.repo.fetch_point_in_time_candles(
                instrument_id="instrument-1", timeframe_seconds=300,
                start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                end_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                max_observation_delay_seconds=300,
            )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].candle.close, 101)
        self.assertEqual(result[0].content_hash, "a" * 64)
        request = urlopen.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/rpc/get_point_in_time_market_candles"))
        self.assertEqual(request.get_method(), "POST")
        payload = json.loads(request.data.decode())
        self.assertEqual(payload["p_max_observation_delay_seconds"], 300)
        self.assertNotIn("server-only-test-secret", request.full_url)

    def test_snapshot_insert_is_idempotent_and_fallback_queries_by_hash(self):
        snapshot = sample_snapshot()
        with patch("quant.market_engine.research_persistence.urlopen",
                   side_effect=[FakeResponse([]), FakeResponse([{"id": "snapshot-id"}])]) as urlopen:
            snapshot_id = self.repo.append_portfolio_snapshot(snapshot)
        self.assertEqual(snapshot_id, "snapshot-id")
        post_request = urlopen.call_args_list[0].args[0]
        self.assertEqual(post_request.get_method(), "POST")
        self.assertIn("on_conflict=portfolio_id%2Cas_of%2Csource%2Cstate_hash", post_request.full_url)
        self.assertIn(snapshot.state_hash, post_request.data.decode())
        get_request = urlopen.call_args_list[1].args[0]
        self.assertEqual(get_request.get_method(), "GET")
        self.assertIn("state_hash", get_request.full_url)

    def test_as_of_query_requires_both_effective_and_observed_time(self):
        with patch("quant.market_engine.research_persistence.urlopen", return_value=FakeResponse([])) as urlopen:
            result = self.repo.latest_portfolio_snapshot_as_of(
                portfolio_id="portfolio-1", decision_time=datetime(2025, 1, 1, tzinfo=timezone.utc)
            )
        self.assertIsNone(result)
        url = urlopen.call_args.args[0].full_url
        self.assertIn("as_of=lte.", url)
        self.assertIn("observed_at=lte.", url)


if __name__ == "__main__":
    unittest.main()
