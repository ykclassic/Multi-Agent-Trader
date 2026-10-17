from datetime import datetime, timezone
import unittest

from scripts.market_data_worker import PersistentProviderCircuitBreaker


class FakeCircuitBreaker(PersistentProviderCircuitBreaker):
    def __init__(self):
        super().__init__(
            supabase_url="https://example.supabase.co",
            service_role_key="server-secret",
            provider="twelvedata_forex_time_series",
            failure_threshold=3,
            cooldown_minutes=15,
        )
        self.state = {
            "provider": self.provider,
            "consecutive_failures": 0,
            "opened_until": None,
            "last_success_at": None,
        }

    def read(self):
        return dict(self.state)

    def _write(self, state):
        self.state = dict(state)


class MarketDataWorkerTests(unittest.TestCase):
    def test_first_transient_failure_does_not_open_breaker(self):
        breaker = FakeCircuitBreaker()
        result = breaker.failure(RuntimeError("provider timeout"))
        self.assertEqual(result["consecutive_failures"], 1)
        self.assertIsNone(result["opened_until"])

    def test_repeated_failures_open_breaker(self):
        breaker = FakeCircuitBreaker()
        breaker.failure(RuntimeError("provider timeout"))
        breaker.failure(RuntimeError("provider timeout"))
        result = breaker.failure(RuntimeError("provider timeout"))
        self.assertEqual(result["consecutive_failures"], 3)
        self.assertIsNotNone(result["opened_until"])

    def test_rate_limit_opens_breaker_immediately_for_longer_cooldown(self):
        breaker = FakeCircuitBreaker()
        result = breaker.failure(RuntimeError("provider returned HTTP 429"))
        self.assertEqual(result["consecutive_failures"], 1)
        opened = datetime.fromisoformat(result["opened_until"])
        self.assertGreater((opened - datetime.now(timezone.utc)).total_seconds(), 59 * 60)

    def test_success_resets_failure_state(self):
        breaker = FakeCircuitBreaker()
        breaker.failure(RuntimeError("provider timeout"))
        breaker.success()
        self.assertEqual(breaker.state["consecutive_failures"], 0)
        self.assertIsNone(breaker.state["opened_until"])
        self.assertIsNotNone(breaker.state["last_success_at"])


if __name__ == "__main__":
    unittest.main()
