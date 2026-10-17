from datetime import datetime, timedelta, timezone
import unittest

from quant.market_engine import Candle
from quant.market_engine.quality import score_candle_batch


class MarketDataQualityTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.candles = [
            Candle(self.now - timedelta(hours=3 - i), 100 + i, 101 + i, 99 + i, 100 + i, 10)
            for i in range(4)
        ]

    def test_complete_fresh_batch_scores_high(self):
        result = score_candle_batch(self.candles, source="test-feed", as_of=self.now)
        self.assertEqual(result.missing_candle_count, 0)
        self.assertEqual(result.completeness_score, 1.0)
        self.assertEqual(result.freshness_score, 1.0)
        self.assertEqual(result.overall_quality_score, 1.0)
        self.assertFalse(result.is_stale)

    def test_detects_missing_bars_and_stale_latest_data(self):
        candles = [self.candles[0], self.candles[2], self.candles[3]]
        result = score_candle_batch(candles, source="test-feed", as_of=self.now + timedelta(minutes=10), max_age_seconds=180)
        self.assertEqual(result.missing_candle_count, 1)
        self.assertTrue(result.is_stale)
        self.assertEqual(result.freshness_score, 0.0)
        self.assertIn("missing_candles:1", result.issues)
        self.assertIn("stale_latest_candle", result.issues)

    def test_rejects_future_duplicate_unordered_and_empty_batches(self):
        with self.assertRaisesRegex(ValueError, "future-dated"):
            score_candle_batch(self.candles, source="test-feed", as_of=self.now - timedelta(minutes=1))
        with self.assertRaisesRegex(ValueError, "strictly ordered"):
            score_candle_batch([self.candles[0], self.candles[2], self.candles[1]], source="test-feed", as_of=self.now)
        with self.assertRaisesRegex(ValueError, "at least one"):
            score_candle_batch([], source="test-feed", as_of=self.now)

    def test_requires_source_and_timezone(self):
        with self.assertRaisesRegex(ValueError, "source identifier"):
            score_candle_batch(self.candles, source=" ", as_of=self.now)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            score_candle_batch(self.candles, source="test-feed", as_of=datetime(2026, 1, 1, 12, 0))


if __name__ == "__main__":
    unittest.main()
