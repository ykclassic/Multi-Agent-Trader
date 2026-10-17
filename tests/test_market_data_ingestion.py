from datetime import datetime, timedelta, timezone
import unittest

from quant.market_engine.contracts import MarketDataRequest
from quant.market_engine.engine import Candle
from quant.market_engine.ingestion import ingest_candles


class FakeProvider:
    source_id = "test-feed"

    def __init__(self, candles):
        self.candles = candles

    async def fetch_ohlcv(self, request):
        return self.candles


class FakeRepository:
    def __init__(self):
        self.calls = []

    async def upsert_candles(self, **kwargs):
        self.calls.append(kwargs)
        return len(kwargs["candles"])


class MarketDataIngestionTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_quality_and_persistence_pipeline(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        candles = [
            Candle(now - timedelta(hours=3), 100, 102, 99, 101, 10),
            Candle(now - timedelta(hours=2), 101, 103, 100, 102, 11),
        ]
        repository = FakeRepository()
        result = await ingest_candles(
            provider=FakeProvider(candles),
            request=MarketDataRequest("BTC/USDT", 3600, now - timedelta(hours=4), now, 100),
            instrument_id="instrument-uuid", repository=repository, clock=lambda: now,
        )
        self.assertEqual(result.fetched_count, 2)
        self.assertEqual(result.persisted_count, 2)
        self.assertEqual(repository.calls[0]["source"], "test-feed")
        self.assertEqual(repository.calls[0]["quality_score"], result.quality.overall_quality_score)

    async def test_rejects_unclosed_candles_before_persistence(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        candle = Candle(now - timedelta(minutes=30), 100, 102, 99, 101, 10)
        repository = FakeRepository()
        with self.assertRaisesRegex(ValueError, "unclosed candle"):
            await ingest_candles(
                provider=FakeProvider([candle]),
                request=MarketDataRequest("BTC/USDT", 3600, now - timedelta(hours=2), now, 10),
                instrument_id="instrument-uuid", repository=repository, clock=lambda: now,
            )
        self.assertEqual(repository.calls, [])

    async def test_rejects_provider_ordering_errors_before_persistence(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        candles = [
            Candle(now - timedelta(hours=2), 100, 102, 99, 101, 10),
            Candle(now - timedelta(hours=3), 101, 103, 100, 102, 11),
        ]
        repository = FakeRepository()
        with self.assertRaisesRegex(ValueError, "unordered or duplicate"):
            await ingest_candles(
                provider=FakeProvider(candles),
                request=MarketDataRequest("BTC/USDT", 3600, now - timedelta(hours=4), now, 10),
                instrument_id="instrument-uuid", repository=repository, clock=lambda: now,
            )
        self.assertEqual(repository.calls, [])

    async def test_empty_batch_is_a_valid_no_data_result_and_does_not_write_rows(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        repository = FakeRepository()
        result = await ingest_candles(
            provider=FakeProvider([]),
            request=MarketDataRequest("EUR/USD", 3600, now - timedelta(hours=4), now, 10),
            instrument_id="instrument-uuid", repository=repository, clock=lambda: now,
        )
        self.assertEqual(result.fetched_count, 0)
        self.assertEqual(result.persisted_count, 0)
        self.assertIn("empty_candle_batch", result.quality.issues)
        self.assertEqual(repository.calls[0]["candles"], [])


if __name__ == "__main__":
    unittest.main()
