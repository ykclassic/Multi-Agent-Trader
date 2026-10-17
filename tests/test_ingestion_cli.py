import json
from datetime import timezone
import unittest
from unittest.mock import patch

from scripts.ingest_market_data import parse_datetime, resolve_instrument_id


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class IngestionCliTests(unittest.TestCase):
    def test_parse_datetime_requires_and_normalizes_timezone(self):
        value = parse_datetime("2026-10-17T08:00:00+01:00")
        self.assertEqual(value.tzinfo, timezone.utc)
        self.assertEqual(value.hour, 7)

    def test_registry_resolution_returns_exact_active_instrument(self):
        with patch("scripts.ingest_market_data.urlopen", return_value=FakeResponse([{"id": "instrument-123"}])) as opened:
            result = resolve_instrument_id(
                supabase_url="https://example.supabase.co",
                service_role_key="server-secret",
                symbol="EUR/USD",
                venue_code="oanda",
            )
        self.assertEqual(result, "instrument-123")
        request = opened.call_args.args[0]
        self.assertIn("/rest/v1/instruments?", request.full_url)
        self.assertIn("venues.code", request.full_url)

    def test_registry_resolution_fails_closed_on_ambiguous_match(self):
        with patch("scripts.ingest_market_data.urlopen", return_value=FakeResponse([{"id": "a"}, {"id": "b"}])):
            with self.assertRaisesRegex(RuntimeError, "Expected exactly one active instrument"):
                resolve_instrument_id(
                    supabase_url="https://example.supabase.co",
                    service_role_key="server-secret",
                    symbol="EUR/USD",
                    venue_code="oanda",
                )


if __name__ == "__main__":
    unittest.main()
