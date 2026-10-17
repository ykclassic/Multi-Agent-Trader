from datetime import datetime, timedelta, timezone
import unittest

from quant.market_engine.contracts import MarketDataRequest
from quant.market_engine.providers import BinanceSpotProvider, JsonHttpClient, MarketDataProviderError, TwelveDataForexProvider, _RetryableHttpError


class FakeJsonClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def get_json(self, url, params):
        self.calls.append((url, dict(params)))
        return self.payload


class MarketDataProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_binance_maps_symbol_normalizes_rows_and_drops_open_candle(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        start = now - timedelta(hours=3)
        client = FakeJsonClient([
            [int((now - timedelta(hours=2)).timestamp() * 1000), "100", "105", "99", "103", "20"],
            [int((now - timedelta(hours=1)).timestamp() * 1000), "103", "106", "102", "104", "21"],
            [int(now.timestamp() * 1000), "104", "107", "103", "106", "22"],
        ])
        provider = BinanceSpotProvider(client=client, clock=lambda: now)
        request = MarketDataRequest("BTC/USD", 3600, start, now + timedelta(hours=1), 100)
        candles = await provider.fetch_ohlcv(request)
        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0].close, 103.0)
        self.assertEqual(client.calls[0][1]["symbol"], "BTCUSDT")
        self.assertEqual(client.calls[0][1]["interval"], "1h")
        self.assertEqual(candles[0].timestamp.tzinfo, timezone.utc)

    async def test_binance_rejects_malformed_payload(self):
        now = datetime.now(timezone.utc)
        provider = BinanceSpotProvider(client=FakeJsonClient({"unexpected": "object"}), clock=lambda: now)
        request = MarketDataRequest("BTC/USDT", 3600, now - timedelta(hours=3), now, 10)
        with self.assertRaisesRegex(MarketDataProviderError, "unexpected candle payload"):
            await provider.fetch_ohlcv(request)

    async def test_twelve_data_orders_candles_and_uses_zero_for_missing_volume(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        old, older = now - timedelta(hours=2), now - timedelta(hours=3)
        client = FakeJsonClient({"values": [
            {"datetime": old.strftime("%Y-%m-%d %H:%M:%S"), "open": "1.08", "high": "1.09", "low": "1.07", "close": "1.085"},
            {"datetime": older.strftime("%Y-%m-%d %H:%M:%S"), "open": "1.07", "high": "1.08", "low": "1.06", "close": "1.08"},
        ]})
        provider = TwelveDataForexProvider(api_key="test-key", client=client, clock=lambda: now)
        request = MarketDataRequest("EUR/USD", 3600, now - timedelta(days=1), now, 100)
        candles = await provider.fetch_ohlcv(request)
        self.assertEqual([c.timestamp for c in candles], [older, old])
        self.assertEqual(candles[0].volume, 0)
        self.assertEqual(client.calls[0][1]["symbol"], "EUR/USD")
        self.assertEqual(client.calls[0][1]["apikey"], "test-key")
        self.assertEqual(client.calls[0][1]["timezone"], "UTC")

    async def test_twelve_data_requires_key_without_network_call(self):
        provider = TwelveDataForexProvider(api_key="", client=FakeJsonClient({}))
        now = datetime.now(timezone.utc)
        request = MarketDataRequest("EUR/USD", 3600, now - timedelta(hours=2), now, 10)
        with self.assertRaisesRegex(MarketDataProviderError, "TWELVEDATA_API_KEY"):
            await provider.fetch_ohlcv(request)

    async def test_http_429_is_not_retried_by_client(self):
        client = JsonHttpClient(max_retries=3, min_interval_seconds=0)
        attempts = []
        def rate_limited(url):
            attempts.append(url)
            raise _RetryableHttpError(429)
        client._read_json_sync = rate_limited
        with self.assertRaisesRegex(MarketDataProviderError, "HTTP 429"):
            await client.get_json("https://example.test", {})
        self.assertEqual(len(attempts), 1)

    async def test_request_must_be_timezone_aware(self):
        provider = BinanceSpotProvider(client=FakeJsonClient([]))
        request = MarketDataRequest("BTC/USDT", 3600, datetime(2026, 1, 1), datetime(2026, 1, 2, tzinfo=timezone.utc))
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            await provider.fetch_ohlcv(request)


if __name__ == "__main__":
    unittest.main()
