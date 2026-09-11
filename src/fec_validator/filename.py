"""File name conventions: ``<SIREN>FEC<AAAAMMJJ>.<ext>`` and the fiscal period."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

from fec_validator.models import FiscalPeriod
from fec_validator.parsing import parse_date

_FILENAME_RE = re.compile(r"(?P<siren>\d{9})FEC(?P<closing>\d{8})", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class FileNameInfo:
    """Information extracted from a conforming file name."""

    siren: str
    closing_raw: str
    closing_date: date | None

    @property
    def siren_valid(self) -> bool:
        """True when the SIREN passes the Luhn check."""
        return luhn_valid(self.siren)


def parse_filename(name: str) -> FileNameInfo | None:
    """Parse a FEC file name. Return ``None`` when it does not follow the convention.

    The extension is ignored (``.txt`` and ``.csv`` are both common).
    """
    stem = name.split(".", 1)[0]
    match = _FILENAME_RE.fullmatch(stem)
    if match is None:
        return None
    closing_raw = match["closing"]
    return FileNameInfo(match["siren"], closing_raw, parse_date(closing_raw))


def luhn_valid(number: str) -> bool:
    """Check a digit string with the Luhn algorithm (used by SIREN numbers)."""
    if not number.isdigit():
        return False
    total = 0
    for index, char in enumerate(reversed(number)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def previous_closing(end: date) -> date:
    """Closing date of the previous 12 month fiscal year.

    A closing on the last day of a month is followed by a closing on the last
    day of the same month one year earlier (28 February after 29 February).
    """
    last_day = calendar.monthrange(end.year, end.month)[1]
    previous_last_day = calendar.monthrange(end.year - 1, end.month)[1]
    if end.day == last_day:
        return date(end.year - 1, end.month, previous_last_day)
    return date(end.year - 1, end.month, min(end.day, previous_last_day))


def resolve_period(
    info: FileNameInfo | None,
    start: date | None = None,
    end: date | None = None,
) -> FiscalPeriod:
    """Combine explicit bounds and the closing date found in the file name.

    Explicit values win. When only the end is known, the start is inferred
    assuming a 12 month fiscal year and flagged as such.
    """
    if end is None and info is not None:
        end = info.closing_date
    if start is not None or end is None:
        return FiscalPeriod(start=start, end=end, start_inferred=False)
    return FiscalPeriod(
        start=previous_closing(end) + timedelta(days=1),
        end=end,
        start_inferred=True,
    )
