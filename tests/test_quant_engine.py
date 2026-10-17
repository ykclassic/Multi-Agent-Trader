from datetime import datetime, timedelta, timezone
import unittest

from quant.market_engine import Candle, assess_position_risk, build_market_snapshot


class QuantEngineTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.candles = []
        for index in range(40):
            close = 100.0 + index * 0.5
            self.candles.append(Candle(
                timestamp=self.now - timedelta(hours=39 - index),
                open=close - 0.2,
                high=close + 0.4,
                low=close - 0.4,
                close=close,
                volume=1000.0 + index,
            ))

    def test_snapshot_is_deterministic_and_uptrend_is_classified(self):
        snapshot = build_market_snapshot(self.candles, as_of=self.now, max_age_seconds=180)
        again = build_market_snapshot(self.candles, as_of=self.now, max_age_seconds=180)
        self.assertEqual(snapshot, again)
        self.assertEqual(snapshot.regime, "trend_up")
        self.assertGreater(snapshot.ema_fast, snapshot.ema_slow)
        self.assertGreaterEqual(snapshot.rsi_14, 0)
        self.assertLessEqual(snapshot.rsi_14, 100)
        self.assertGreater(snapshot.atr_14, 0)
        self.assertEqual(snapshot.candle_count, 40)

    def test_rejects_stale_market_data(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            build_market_snapshot(self.candles, as_of=self.now + timedelta(minutes=5), max_age_seconds=180)

    def test_rejects_future_candle(self):
        candles = list(self.candles)
        candles[-1] = Candle(self.now + timedelta(minutes=1), 120, 121, 119, 120, 1)
        with self.assertRaisesRegex(ValueError, "future-dated"):
            build_market_snapshot(candles, as_of=self.now, max_age_seconds=180)

    def test_rejects_unordered_and_invalid_ohlcv(self):
        with self.assertRaisesRegex(ValueError, "strictly ordered"):
            build_market_snapshot([self.candles[0], self.candles[2], self.candles[1]] + self.candles[3:], as_of=self.now)
        bad = Candle(self.now, 100, 99, 98, 101, 1)
        with self.assertRaisesRegex(ValueError, "High must"):
            bad.validate()

    def test_position_size_obeys_risk_budget(self):
        result = assess_position_risk(equity=10_000, entry_price=100, stop_price=95, side="long")
        self.assertTrue(result.allowed)
        self.assertAlmostEqual(result.estimated_loss_at_stop, 50.0)
        self.assertLessEqual(result.risk_fraction_of_equity, 0.005)
        self.assertLessEqual(result.notional, 10_000)

    def test_rejects_invalid_stop_and_risk_parameters(self):
        result = assess_position_risk(equity=10_000, entry_price=100, stop_price=101, side="long")
        self.assertFalse(result.allowed)
        self.assertIn("Stop must", result.reason)
        too_risky = assess_position_risk(equity=10_000, entry_price=100, stop_price=90, side="long", risk_fraction=0.05)
        self.assertFalse(too_risky.allowed)


if __name__ == "__main__":
    unittest.main()
