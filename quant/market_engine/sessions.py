"""Session calendars for market-data completeness scoring.

The default FX session is the common New York 17:00 Sunday open to Friday
17:00 close. Holiday dates and early closes are configurable because FX holiday
liquidity/availability is provider- and jurisdiction-dependent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class ForexSessionCalendar:
    timezone_name: str = "America/New_York"
    holidays: frozenset[date] = frozenset()
    early_closes: dict[date, time] = field(default_factory=dict)
    sunday_open: time = time(17, 0)
    friday_close: time = time(17, 0)

    def is_open(self, timestamp: datetime) -> bool:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Session timestamps must be timezone-aware")
        local = timestamp.astimezone(ZoneInfo(self.timezone_name))
        day = local.date()
        if day in self.holidays:
            return False
        if local.weekday() == 5:  # Saturday
            return False
        if local.weekday() == 6:  # Sunday opens at 17:00 New York time
            return local.timetz().replace(tzinfo=None) >= self.sunday_open
        if local.weekday() == 4:  # Friday closes at 17:00, or configured early close
            close_at = self.early_closes.get(day, self.friday_close)
            return local.timetz().replace(tzinfo=None) < close_at
        if day in self.early_closes:
            return local.timetz().replace(tzinfo=None) < self.early_closes[day]
        return True
    def trading_seconds_between(self, start: datetime, end: datetime) -> float:
        """Return elapsed wall-clock seconds that fall inside expected FX sessions.

        Fifteen-minute sampling is used only for age/freshness metadata; candle-gap
        counting itself evaluates each expected candle timestamp exactly.
        """
        if start.tzinfo is None or start.utcoffset() is None or end.tzinfo is None or end.utcoffset() is None:
            raise ValueError("Session timestamps must be timezone-aware")
        if end <= start:
            return 0.0
        from datetime import timedelta
        cursor = start
        elapsed = 0.0
        step = timedelta(minutes=15)
        while cursor < end:
            next_cursor = min(cursor + step, end)
            midpoint = cursor + (next_cursor - cursor) / 2
            if self.is_open(midpoint):
                elapsed += (next_cursor - cursor).total_seconds()
            cursor = next_cursor
        return elapsed

