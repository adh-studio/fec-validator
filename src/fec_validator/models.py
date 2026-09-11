"""Core value objects shared by every layer."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date


class Severity(enum.StrEnum):
    """How serious an issue is. Only errors make a file non compliant."""

    ERROR = "error"
    WARNING = "warning"

    @property
    def label(self) -> str:
        """French label used in human readable reports."""
        return "ERREUR" if self is Severity.ERROR else "AVERTISSEMENT"


class Scope(enum.StrEnum):
    """What a rule looks at."""

    FILE = "file"
    LINE = "line"
    ENTRY = "entry"
    GLOBAL = "global"

    @property
    def label(self) -> str:
        """French label used in human readable reports."""
        return {
            Scope.FILE: "fichier",
            Scope.LINE: "ligne",
            Scope.ENTRY: "écriture",
            Scope.GLOBAL: "global",
        }[self]


@dataclass(frozen=True, slots=True)
class Issue:
    """A single finding produced by a rule."""

    code: str
    severity: Severity
    message: str
    line: int | None = None
    column: str | None = None
    entry: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize to plain JSON compatible types."""
        return {
            "code": self.code,
            "severity": self.severity.value,
            "line": self.line,
            "column": self.column,
            "entry": self.entry,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class FiscalPeriod:
    """Fiscal year boundaries. Any bound may be unknown.

    ``start_inferred`` is true when the start date was deduced from the closing
    date (assuming a 12 month fiscal year) instead of being given explicitly.
    """

    start: date | None = None
    end: date | None = None
    start_inferred: bool = False

    @property
    def is_known(self) -> bool:
        """True when at least one bound is known."""
        return self.start is not None or self.end is not None


@dataclass(slots=True)
class FecLine:
    """One data line of the FEC, already split into fields.

    ``fields`` maps canonical column names to stripped values. ``raw_count`` is
    the number of fields actually found on the line, which may differ from the
    number of columns when the line is malformed.
    """

    number: int
    fields: dict[str, str]
    raw_count: int

    def get(self, column: str) -> str:
        """Return the value of ``column`` or an empty string when absent."""
        return self.fields.get(column, "")

    @property
    def entry_key(self) -> tuple[str, str]:
        """Key identifying the accounting entry (écriture) of this line."""
        return (self.get("JournalCode"), self.get("EcritureNum"))


def entry_label(key: tuple[str, str]) -> str:
    """Human readable identifier of an entry, e.g. ``VT/000042``."""
    return f"{key[0]}/{key[1]}"
