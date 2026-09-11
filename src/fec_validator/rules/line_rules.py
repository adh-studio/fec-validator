"""Line level rules. Each rule looks at a single line and nothing else."""

from __future__ import annotations

import re
from collections.abc import Iterator

from fec_validator.columns import (
    AMOUNT_COLUMNS_BY_LAYOUT,
    MANDATORY_COLUMNS,
    OPTIONAL_DATE_COLUMNS,
    REQUIRED_DATE_COLUMNS,
    Layout,
)
from fec_validator.context import ValidationContext
from fec_validator.models import FecLine, Issue, Severity
from fec_validator.parsing import ZERO, amount_hint, format_date_fr, parse_amount, parse_date
from fec_validator.parsing import parse_sens as _parse_sens
from fec_validator.rules.base import LineRule, register

_CURRENCY_RE = re.compile(r"[A-Z]{3}")


@register
class FieldCountRule(LineRule):
    """A line must have as many fields as the header."""

    code = "FEC-L001"
    severity = Severity.ERROR
    title = "Nombre de champs différent de l'en-tête"
    structural = True

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        expected = ctx.column_count
        if line.raw_count != expected:
            yield self.issue(
                f"{line.raw_count} champs trouvés, {expected} attendus "
                "(séparateur présent dans une valeur ou colonne manquante). "
                "Les autres contrôles de la ligne sont ignorés.",
                line=line.number,
            )


@register
class MandatoryFieldsRule(LineRule):
    """Mandatory fields must not be empty."""

    code = "FEC-L002"
    severity = Severity.ERROR
    title = "Champ obligatoire vide"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        fields = line.fields
        for column in MANDATORY_COLUMNS:
            if not fields.get(column):
                yield self.issue(
                    f"Le champ obligatoire {column} est vide.", line=line.number, column=column
                )


@register
class DateFormatRule(LineRule):
    """Dates must be valid calendar dates written AAAAMMJJ."""

    code = "FEC-L003"
    severity = Severity.ERROR
    title = "Date invalide (format AAAAMMJJ attendu)"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        fields = line.fields
        for column in (*REQUIRED_DATE_COLUMNS, *OPTIONAL_DATE_COLUMNS):
            value = fields.get(column, "")
            if value and parse_date(value) is None:
                yield self.issue(
                    f"{column} '{value}' n'est pas une date valide au format AAAAMMJJ.",
                    line=line.number,
                    column=column,
                )


@register
class AmountFormatRule(LineRule):
    """Amounts use a comma as decimal separator and no thousands separator."""

    code = "FEC-L004"
    severity = Severity.ERROR
    title = "Montant mal formé (virgule décimale, sans séparateur de milliers)"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        fields = line.fields
        for column in AMOUNT_COLUMNS_BY_LAYOUT[ctx.layout]:
            value = fields.get(column, "")
            if parse_amount(value) is None:
                yield self.issue(
                    f"{column} '{value}' n'est pas un montant valide : {amount_hint(value)}.",
                    line=line.number,
                    column=column,
                )


@register
class DebitAndCreditRule(LineRule):
    """A line is either a debit or a credit, not both."""

    code = "FEC-L005"
    severity = Severity.ERROR
    title = "Débit et crédit renseignés sur la même ligne"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        if ctx.layout is not Layout.DEBIT_CREDIT:
            return
        debit = parse_amount(line.get("Debit"))
        credit = parse_amount(line.get("Credit"))
        if debit and credit:
            yield self.issue(
                f"Débit ({line.get('Debit')}) et crédit ({line.get('Credit')}) sont tous "
                "deux non nuls sur la même ligne.",
                line=line.number,
            )


@register
class SensRule(LineRule):
    """In the Montant/Sens layout, Sens is D/C (or +1/-1)."""

    code = "FEC-L006"
    severity = Severity.ERROR
    title = "Sens invalide (D, C, +1 ou -1 attendu)"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        if ctx.layout is not Layout.MONTANT_SENS:
            return
        value = line.get("Sens")
        if _parse_sens(value) is None:
            yield self.issue(
                f"Sens '{value}' invalide : D ou C (ou +1 / -1) attendu.",
                line=line.number,
                column="Sens",
            )


@register
class NegativeAmountRule(LineRule):
    """Debit, Credit and Montant are expected to be positive."""

    code = "FEC-L007"
    severity = Severity.WARNING
    title = "Montant négatif"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        columns = ("Debit", "Credit") if ctx.layout is Layout.DEBIT_CREDIT else ("Montant",)
        for column in columns:
            amount = parse_amount(line.get(column))
            if amount is not None and amount < ZERO:
                yield self.issue(
                    f"{column} négatif ({line.get(column)}) : un montant positif dans l'autre "
                    "colonne est attendu.",
                    line=line.number,
                    column=column,
                )


@register
class LettrageDateRule(LineRule):
    """A lettered line should carry its lettering date."""

    code = "FEC-L008"
    severity = Severity.WARNING
    title = "EcritureLet renseigné sans DateLet"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        if line.get("EcritureLet") and not line.get("DateLet"):
            yield self.issue(
                f"Lettrage '{line.get('EcritureLet')}' sans date de lettrage (DateLet vide).",
                line=line.number,
                column="DateLet",
            )


@register
class AuxiliaryLabelRule(LineRule):
    """An auxiliary account number needs its label."""

    code = "FEC-L009"
    severity = Severity.ERROR
    title = "CompAuxNum renseigné sans CompAuxLib"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        if line.get("CompAuxNum") and not line.get("CompAuxLib"):
            yield self.issue(
                f"Compte auxiliaire '{line.get('CompAuxNum')}' sans libellé (CompAuxLib vide).",
                line=line.number,
                column="CompAuxLib",
            )


@register
class CurrencyConsistencyRule(LineRule):
    """Montantdevise and Idevise go together."""

    code = "FEC-L010"
    severity = Severity.WARNING
    title = "Montantdevise et Idevise incohérents"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        raw_amount = line.get("Montantdevise")
        currency = line.get("Idevise")
        amount = parse_amount(raw_amount)
        has_amount = bool(raw_amount) and amount != ZERO
        if has_amount and not currency:
            yield self.issue(
                f"Montantdevise renseigné ({raw_amount}) sans code devise (Idevise vide).",
                line=line.number,
                column="Idevise",
            )
        elif currency and not has_amount:
            yield self.issue(
                f"Idevise renseigné ({currency}) sans montant en devise (Montantdevise vide "
                "ou nul).",
                line=line.number,
                column="Montantdevise",
            )


@register
class CurrencyCodeRule(LineRule):
    """Idevise should be an ISO 4217 code (three upper case letters)."""

    code = "FEC-L011"
    severity = Severity.WARNING
    title = "Idevise hors format ISO 4217 (trois lettres majuscules)"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        currency = line.get("Idevise")
        if currency and _CURRENCY_RE.fullmatch(currency) is None:
            yield self.issue(
                f"Idevise '{currency}' n'est pas un code ISO 4217 (ex. EUR, USD).",
                line=line.number,
                column="Idevise",
            )


@register
class FiscalYearRule(LineRule):
    """EcritureDate must fall within the known bounds of the fiscal year."""

    code = "FEC-L012"
    severity = Severity.ERROR
    title = "EcritureDate hors de l'exercice"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        period = ctx.period
        value = parse_date(line.get("EcritureDate"))
        if value is None:
            return
        if period.end is not None and value > period.end:
            yield self.issue(
                f"EcritureDate {format_date_fr(value)} postérieure à la clôture de l'exercice "
                f"({format_date_fr(period.end)}).",
                line=line.number,
                column="EcritureDate",
            )
        elif period.start is not None and not period.start_inferred and value < period.start:
            yield self.issue(
                f"EcritureDate {format_date_fr(value)} antérieure au début de l'exercice "
                f"({format_date_fr(period.start)}).",
                line=line.number,
                column="EcritureDate",
            )


@register
class InferredStartRule(LineRule):
    """Dates before a start date deduced from a 12 month assumption are only suspicious."""

    code = "FEC-L013"
    severity = Severity.WARNING
    title = "EcritureDate antérieure au début d'exercice supposé (12 mois)"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        period = ctx.period
        if period.start is None or not period.start_inferred:
            return
        value = parse_date(line.get("EcritureDate"))
        if value is not None and value < period.start:
            yield self.issue(
                f"EcritureDate {format_date_fr(value)} antérieure au {format_date_fr(period.start)}"
                ", début supposé d'un exercice de 12 mois. Préciser --debut si l'exercice "
                "est plus long.",
                line=line.number,
                column="EcritureDate",
            )


@register
class ValidDateRule(LineRule):
    """An entry is normally validated on or after its accounting date."""

    code = "FEC-L014"
    severity = Severity.WARNING
    title = "ValidDate antérieure à EcritureDate"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        entry_date = parse_date(line.get("EcritureDate"))
        valid_date = parse_date(line.get("ValidDate"))
        if entry_date is not None and valid_date is not None and valid_date < entry_date:
            yield self.issue(
                f"ValidDate {format_date_fr(valid_date)} antérieure à EcritureDate "
                f"{format_date_fr(entry_date)}.",
                line=line.number,
                column="ValidDate",
            )
