"""Whole file rules, run on the final totals."""

from __future__ import annotations

from collections.abc import Iterator

from fec_validator.aggregation import Totals
from fec_validator.context import ValidationContext
from fec_validator.models import Issue, Severity
from fec_validator.parsing import format_amount_fr
from fec_validator.rules.base import GlobalRule, register


@register
class BalancedFileRule(GlobalRule):
    """Total debit equals total credit over the whole file."""

    code = "FEC-G001"
    severity = Severity.ERROR
    title = "Total des débits différent du total des crédits"

    def check(self, totals: Totals, ctx: ValidationContext) -> Iterator[Issue]:
        if totals.debit == totals.credit:
            return
        note = ""
        if totals.invalid_amount_lines:
            note = f" (hors {totals.invalid_amount_lines} ligne(s) au montant illisible)"
        yield self.issue(
            f"Total débit {format_amount_fr(totals.debit)} différent du total crédit "
            f"{format_amount_fr(totals.credit)}, écart "
            f"{format_amount_fr(totals.debit - totals.credit)}{note}."
        )


@register
class EmptyFileRule(GlobalRule):
    """A FEC is expected to contain at least one entry line."""

    code = "FEC-G002"
    severity = Severity.WARNING
    title = "Aucune ligne d'écriture"

    def check(self, totals: Totals, ctx: ValidationContext) -> Iterator[Issue]:
        if totals.line_count == 0:
            yield self.issue("Le fichier ne contient que la ligne d'en-tête.")
