"""Streaming aggregation: per entry sums and file totals.

Only one small object per accounting entry is kept in memory, never the
lines themselves.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal

from fec_validator.models import FecLine, entry_label
from fec_validator.parsing import ZERO


@dataclass(slots=True)
class EntryAggregate:
    """Running totals of one accounting entry (JournalCode + EcritureNum)."""

    journal_code: str
    number: str
    first_line: int
    date: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    line_count: int = 0
    other_date: str | None = None
    other_date_line: int | None = None
    has_invalid_amount: bool = False

    @property
    def label(self) -> str:
        """Human readable identifier, e.g. ``VT/000042``."""
        return entry_label((self.journal_code, self.number))


@dataclass(slots=True)
class Totals:
    """File level figures."""

    line_count: int = 0
    malformed_lines: int = 0
    invalid_amount_lines: int = 0
    entry_count: int = 0
    debit: Decimal = ZERO
    credit: Decimal = ZERO


@dataclass(slots=True)
class Aggregator:
    """Accumulate entries and totals while lines are streamed."""

    entries: dict[tuple[str, str], EntryAggregate] = field(default_factory=dict)
    totals: Totals = field(default_factory=Totals)

    def add_malformed(self) -> None:
        """Count a line that could not be split into the expected fields."""
        self.totals.line_count += 1
        self.totals.malformed_lines += 1

    def add(self, line: FecLine, amounts: tuple[Decimal, Decimal] | None) -> None:
        """Add a well formed line. ``amounts`` is ``None`` when they are unreadable."""
        totals = self.totals
        totals.line_count += 1
        key = line.entry_key
        date = line.get("EcritureDate")
        entry = self.entries.get(key)
        if entry is None:
            entry = EntryAggregate(
                journal_code=sys.intern(key[0]),
                number=key[1],
                first_line=line.number,
                date=sys.intern(date),
            )
            self.entries[key] = entry
        elif date != entry.date and entry.other_date is None:
            entry.other_date = date
            entry.other_date_line = line.number
        entry.line_count += 1
        if amounts is None:
            entry.has_invalid_amount = True
            totals.invalid_amount_lines += 1
            return
        debit, credit = amounts
        entry.debit += debit
        entry.credit += credit
        totals.debit += debit
        totals.credit += credit

    def finish(self) -> Totals:
        """Return the totals, with the number of entries filled in."""
        self.totals.entry_count = len(self.entries)
        return self.totals
