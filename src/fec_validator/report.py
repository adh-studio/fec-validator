"""Issue collection (with a per rule cap) and the validation report."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from fec_validator.aggregation import Totals
from fec_validator.columns import Layout
from fec_validator.filename import FileNameInfo
from fec_validator.models import FiscalPeriod, Issue, Severity
from fec_validator.parsing import format_amount_fr
from fec_validator.reader import SEPARATOR_KEYS

DEFAULT_MAX_ISSUES_PER_RULE = 100


class IssueCollector:
    """Count every issue but only keep the first ``max_per_rule`` of each rule.

    This keeps memory bounded on files with millions of faulty lines while
    the counts stay exact.
    """

    def __init__(self, max_per_rule: int = DEFAULT_MAX_ISSUES_PER_RULE) -> None:
        if max_per_rule < 0:
            raise ValueError("max_per_rule must be positive or zero")
        self.max_per_rule = max_per_rule
        self.issues: list[Issue] = []
        self.counts: Counter[str] = Counter()
        self.error_count = 0
        self.warning_count = 0

    def add(self, issue: Issue) -> None:
        """Record one issue."""
        count = self.counts[issue.code] + 1
        self.counts[issue.code] = count
        if issue.severity is Severity.ERROR:
            self.error_count += 1
        else:
            self.warning_count += 1
        if count <= self.max_per_rule:
            self.issues.append(issue)

    def extend(self, issues: Iterable[Issue]) -> None:
        """Record several issues."""
        for issue in issues:
            self.add(issue)


@dataclass(slots=True)
class ValidationReport:
    """Everything the validator found out about a file."""

    path: Path
    encoding: str
    separator: str | None
    layout: Layout | None
    filename: FileNameInfo | None
    period: FiscalPeriod
    totals: Totals
    issues: list[Issue]
    counts: dict[str, int]
    error_count: int
    warning_count: int
    fatal: bool
    max_issues_per_rule: int
    duration_seconds: float = 0.0

    @property
    def is_valid(self) -> bool:
        """True when no error was found (warnings are allowed)."""
        return self.error_count == 0

    @property
    def truncated(self) -> bool:
        """True when some issues were counted but not kept in detail."""
        return any(count > self.max_issues_per_rule for count in self.counts.values())

    def exit_code(self, *, strict: bool = False) -> int:
        """CLI exit code: 0 when compliant, 1 otherwise (warnings too when ``strict``)."""
        if self.error_count or (strict and self.warning_count):
            return 1
        return 0

    def to_dict(self) -> dict[str, object]:
        """Serialize to JSON compatible types. Amounts are strings to keep precision."""
        info = self.filename
        return {
            "file": str(self.path),
            "valid": self.is_valid,
            "fatal": self.fatal,
            "metadata": {
                "encoding": self.encoding,
                "separator": SEPARATOR_KEYS.get(self.separator or ""),
                "layout": self.layout.value if self.layout else None,
                "siren": info.siren if info else None,
                "siren_valid": info.siren_valid if info else None,
                "closing_date": info.closing_date.isoformat()
                if info and info.closing_date
                else None,
                "period": {
                    "start": self.period.start.isoformat() if self.period.start else None,
                    "end": self.period.end.isoformat() if self.period.end else None,
                    "start_inferred": self.period.start_inferred,
                },
            },
            "statistics": {
                "lines": self.totals.line_count,
                "malformed_lines": self.totals.malformed_lines,
                "entries": self.totals.entry_count,
                "total_debit": f"{self.totals.debit:f}",
                "total_credit": f"{self.totals.credit:f}",
            },
            "summary": {
                "errors": self.error_count,
                "warnings": self.warning_count,
                "by_rule": dict(sorted(self.counts.items())),
                "max_issues_per_rule": self.max_issues_per_rule,
                "truncated": self.truncated,
            },
            "issues": [issue.to_dict() for issue in self.issues],
            "duration_seconds": round(self.duration_seconds, 3),
        }

    def summary_line(self) -> str:
        """One line French summary."""
        verdict = "conforme" if self.is_valid else "non conforme"
        return (
            f"{self.path.name} : {verdict} ({self.error_count} erreur(s), "
            f"{self.warning_count} avertissement(s), {self.totals.line_count} lignes, "
            f"débit {format_amount_fr(self.totals.debit)}, "
            f"crédit {format_amount_fr(self.totals.credit)})"
        )
