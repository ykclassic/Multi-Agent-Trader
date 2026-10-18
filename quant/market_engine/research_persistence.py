"""Service-role persistence and point-in-time candle loading for research jobs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .engine import Candle
from .portfolio_state import PortfolioStateSnapshot
from .walk_forward import WalkForwardResult


class ResearchPersistenceError(RuntimeError):
    """Sanitized research storage error; never includes request headers or secrets."""


@dataclass(frozen=True, slots=True)
class PointInTimeCandle:
    candle: Candle
    observed_at: datetime
    content_hash: str
    quality_score: float | None


class SupabaseRestResearchRepository:
    """Trusted server-side access to point-in-time revisions and append-only results."""

    def __init__(self, *, supabase_url: str, service_role_key: str, timeout_seconds: float = 20.0):
        if not supabase_url.startswith("https://") or not service_role_key.strip():
            raise ValueError("A valid Supabase URL and server-only service key are required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.base_url = supabase_url.rstrip("/")
        self.key = service_role_key
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "SupabaseRestResearchRepository":
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise ResearchPersistenceError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        return cls(supabase_url=url, service_role_key=key)

    def _request_json(self, method: str, url: str, payload: Any = None, *,
                      prefer: str | None = None) -> Any:
        headers = {
            "apikey": self.key, "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
        }
        data = None
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer
        request = Request(url, data=data, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else None
        except HTTPError as exc:
            if exc.code == 409:
                raise ResearchPersistenceError("Research persistence rejected a duplicate or conflicting record") from None
            raise ResearchPersistenceError(f"Supabase research request failed with HTTP {exc.code}") from None
        except (URLError, UnicodeDecodeError, json.JSONDecodeError, TimeoutError):
            raise ResearchPersistenceError("Supabase research storage is unavailable or returned invalid JSON") from None

    def fetch_point_in_time_candles(self, *, instrument_id: str, timeframe_seconds: int,
                                    start_at: datetime, end_at: datetime,
                                    max_observation_delay_seconds: int = 300) -> tuple[PointInTimeCandle, ...]:
        if not instrument_id.strip() or timeframe_seconds <= 0:
            raise ValueError("instrument_id and positive timeframe_seconds are required")
        if start_at.tzinfo is None or end_at.tzinfo is None or start_at >= end_at:
            raise ValueError("start_at and end_at must be ordered timezone-aware datetimes")
        if not 0 <= max_observation_delay_seconds <= 86400:
            raise ValueError("max_observation_delay_seconds must be between 0 and 86400")
        url = f"{self.base_url}/rest/v1/rpc/get_point_in_time_market_candles"
        rows = self._request_json("POST", url, {
            "p_instrument_id": instrument_id,
            "p_timeframe_seconds": timeframe_seconds,
            "p_start_at": start_at.astimezone(timezone.utc).isoformat(),
            "p_end_at": end_at.astimezone(timezone.utc).isoformat(),
            "p_max_observation_delay_seconds": max_observation_delay_seconds,
        })
        if not isinstance(rows, list):
            raise ResearchPersistenceError("Point-in-time candle query returned an invalid response")
        result: list[PointInTimeCandle] = []
        for row in rows:
            timestamp = datetime.fromisoformat(row["candle_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
            observed = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
            candle = Candle(timestamp, float(row["open"]), float(row["high"]), float(row["low"]),
                            float(row["close"]), float(row["volume"]))
            candle.validate()
            result.append(PointInTimeCandle(
                candle=candle, observed_at=observed, content_hash=str(row["content_hash"]),
                quality_score=float(row["quality_score"]) if row.get("quality_score") is not None else None,
            ))
        if any(right.candle.timestamp <= left.candle.timestamp for left, right in zip(result, result[1:])):
            raise ResearchPersistenceError("Point-in-time candle query returned duplicate or unordered candles")
        return tuple(result)

    def append_portfolio_snapshot(self, snapshot: PortfolioStateSnapshot) -> str | None:
        row = snapshot.as_row()
        url = f"{self.base_url}/rest/v1/portfolio_state_snapshots"
        rows = self._request_json("POST", url, row, prefer="resolution=ignore-duplicates,return=representation")
        if isinstance(rows, list) and rows:
            return str(rows[0]["id"])
        # An empty representation means an identical immutable snapshot already exists.
        params = urlencode({
            "select": "id", "portfolio_id": f"eq.{snapshot.portfolio_id}",
            "as_of": f"eq.{row['as_of']}", "source": f"eq.{snapshot.source}",
            "state_hash": f"eq.{snapshot.state_hash}", "limit": "1",
        })
        found = self._request_json("GET", f"{url}?{params}")
        if isinstance(found, list) and found:
            return str(found[0]["id"])
        raise ResearchPersistenceError("Portfolio snapshot was not persisted or found after an idempotent insert")

    def latest_portfolio_snapshot_as_of(self, *, portfolio_id: str,
                                        decision_time: datetime) -> dict[str, Any] | None:
        if decision_time.tzinfo is None or decision_time.utcoffset() is None:
            raise ValueError("decision_time must be timezone-aware")
        timestamp = decision_time.astimezone(timezone.utc).isoformat()
        params = urlencode({
            "select": "*", "portfolio_id": f"eq.{portfolio_id}",
            "as_of": f"lte.{timestamp}", "observed_at": f"lte.{timestamp}",
            "order": "as_of.desc,observed_at.desc", "limit": "1",
        })
        rows = self._request_json("GET", f"{self.base_url}/rest/v1/portfolio_state_snapshots?{params}")
        if not isinstance(rows, list):
            raise ResearchPersistenceError("Portfolio state query returned an invalid response")
        return rows[0] if rows else None

    def append_walk_forward_result(self, result: WalkForwardResult, *, workspace_id: str,
                                   asset_class: str, instrument_id: str | None,
                                   instrument_symbol: str, timeframe_seconds: int) -> str | None:
        row = result.as_row(
            workspace_id=workspace_id, asset_class=asset_class, instrument_id=instrument_id,
            instrument_symbol=instrument_symbol, timeframe_seconds=timeframe_seconds,
        )
        url = f"{self.base_url}/rest/v1/walk_forward_runs"
        rows = self._request_json("POST", url, row, prefer="resolution=ignore-duplicates,return=representation")
        if isinstance(rows, list) and rows:
            return str(rows[0]["id"])
        params = urlencode({"select": "id", "workspace_id": f"eq.{workspace_id}",
                            "run_hash": f"eq.{result.run_hash}", "limit": "1"})
        found = self._request_json("GET", f"{url}?{params}")
        if isinstance(found, list) and found:
            return str(found[0]["id"])
        raise ResearchPersistenceError("Walk-forward result was not persisted or found after an idempotent insert")
