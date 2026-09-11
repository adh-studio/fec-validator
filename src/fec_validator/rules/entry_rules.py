"""Entry level rules, run once all the lines of the file have been aggregated."""

from __future__ import annotations

from collections.abc import Iterator

from fec_validator.aggregation import EntryAggregate
from fec_validator.context import ValidationContext
from fec_validator.models import Issue, Severity
from fec_validator.parsing import format_amount_fr
from fec_validator.rules.base import EntryRule, register


@register
class BalancedEntryRule(EntryRule):
    """Within an entry, total debit equals total credit."""

    code = "FEC-E001"
    severity = Severity.ERROR
    title = "Écriture déséquilibrée (débit différent du crédit)"

    def check(self, entry: EntryAggregate, ctx: ValidationContext) -> Iterator[Issue]:
        # An unreadable amount is already reported on its line: comparing the
        # remaining amounts would only add noise.
        if entry.has_invalid_amount or entry.debit == entry.credit:
            return
        gap = entry.debit - entry.credit
        yield self.issue(
            f"Écriture {entry.label} déséquilibrée : débit {format_amount_fr(entry.debit)}, "
            f"crédit {format_amount_fr(entry.credit)}, écart {format_amount_fr(gap)} "
            f"({entry.line_count} lignes).",
            line=entry.first_line,
            entry=entry.label,
        )


@register
class SingleDateRule(EntryRule):
    """All the lines of an entry share the same EcritureDate."""

    code = "FEC-E002"
    severity = Severity.ERROR
    title = "Plusieurs EcritureDate dans une même écriture"

    def check(self, entry: EntryAggregate, ctx: ValidationContext) -> Iterator[Issue]:
        if entry.other_date is not None:
            yield self.issue(
                f"Écriture {entry.label} : EcritureDate '{entry.date}' (ligne "
                f"{entry.first_line}) et '{entry.other_date}' (ligne {entry.other_date_line}).",
                line=entry.other_date_line,
                column="EcritureDate",
                entry=entry.label,
            )
