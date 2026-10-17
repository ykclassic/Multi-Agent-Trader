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
