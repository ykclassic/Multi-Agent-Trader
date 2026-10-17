from datetime import datetime, timedelta, timezone
import unittest

from quant.market_engine.engine import Candle
from quant.market_engine.persistence import SupabaseRestCandleRepository


class RecordingRepository(SupabaseRestCandleRepository):
    def __init__(self):
        super().__init__(supabase_url="https://example.supabase.co", service_role_key="server-secret")
        self.batches = []

    def _post_batch(self, rows):
        self.batches.append(rows)


class CandlePersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_maps_normalized_candles_to_idempotent_upsert_rows(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        candles = [
            Candle(now - timedelta(hours=2), 100, 102, 99, 101, 12),
            Candle(now - timedelta(hours=1), 101, 103, 100, 102, 14),
        ]
        repository = RecordingRepository()
        count = await repository.upsert_candles(
            instrument_id="instrument-id", source="binance_spot_klines",
            timeframe_seconds=3600, candles=candles, quality_score=0.98765,
        )
        self.assertEqual(count, 2)
        self.assertEqual(len(repository.batches), 1)
        rows = repository.batches[0]
        self.assertEqual(rows[0]["instrument_id"], "instrument-id")
        self.assertEqual(rows[0]["source"], "binance_spot_klines")
        self.assertEqual(rows[0]["timeframe_seconds"], 3600)
        self.assertEqual(rows[0]["quality_score"], 0.9877)
        self.assertEqual(rows[0]["data_version"], 1)
        self.assertEqual(rows[0]["is_closed"], True)
        self.assertIn("updated_at", rows[0])
        self.assertEqual(rows[0]["fetched_at"], rows[1]["fetched_at"])

    async def test_empty_batch_is_noop(self):
        repository = RecordingRepository()
        count = await repository.upsert_candles(
            instrument_id="instrument-id", source="test", timeframe_seconds=60,
            candles=[], quality_score=0,
        )
        self.assertEqual(count, 0)
        self.assertEqual(repository.batches, [])

    async def test_rejects_duplicate_or_unordered_candles(self):
        now = datetime.now(timezone.utc)
        candle = Candle(now, 100, 102, 99, 101, 12)
        repository = RecordingRepository()
        with self.assertRaisesRegex(ValueError, "strictly ordered"):
            await repository.upsert_candles(
                instrument_id="instrument-id", source="test", timeframe_seconds=60,
                candles=[candle, candle], quality_score=1,
            )
        self.assertEqual(repository.batches, [])

    async def test_rejects_invalid_quality_score(self):
        repository = RecordingRepository()
        with self.assertRaisesRegex(ValueError, "Quality score"):
            await repository.upsert_candles(
                instrument_id="instrument-id", source="test", timeframe_seconds=60,
                candles=[Candle(datetime.now(timezone.utc), 100, 102, 99, 101, 12)],
                quality_score=1.1,
            )


if __name__ == "__main__":
    unittest.main()
