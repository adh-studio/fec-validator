"""File level rules: name, SIREN, closing date and header."""

from __future__ import annotations

from collections.abc import Iterator

from fec_validator.context import FileContext
from fec_validator.models import Issue, Severity
from fec_validator.rules.base import FileRule, register


@register
class FileNameRule(FileRule):
    """The name must follow ``<SIREN>FEC<AAAAMMJJ>``."""

    code = "FEC-F001"
    severity = Severity.WARNING
    title = "Nom de fichier non conforme (SIREN + FEC + AAAAMMJJ)"

    def check(self, ctx: FileContext) -> Iterator[Issue]:
        if ctx.filename is None:
            yield self.issue(
                f"Le nom '{ctx.path.name}' ne suit pas la forme SirenFECAAAAMMJJ "
                "(exemple : 123456782FEC20251231.txt) ; SIREN et date de clôture "
                "ne peuvent pas être déduits."
            )


@register
class SirenRule(FileRule):
    """The SIREN of the file name must pass the Luhn check."""

    code = "FEC-F002"
    severity = Severity.ERROR
    title = "SIREN invalide (clé de Luhn)"

    def check(self, ctx: FileContext) -> Iterator[Issue]:
        if ctx.filename is not None and not ctx.filename.siren_valid:
            yield self.issue(
                f"Le SIREN {ctx.filename.siren} du nom de fichier est invalide "
                "(la clé de contrôle de Luhn ne correspond pas)."
            )


@register
class ClosingDateRule(FileRule):
    """The closing date of the file name must be a real calendar date."""

    code = "FEC-F003"
    severity = Severity.ERROR
    title = "Date de clôture du nom de fichier invalide"

    def check(self, ctx: FileContext) -> Iterator[Issue]:
        if ctx.filename is not None and ctx.filename.closing_date is None:
            yield self.issue(
                f"La date de clôture '{ctx.filename.closing_raw}' du nom de fichier "
                "n'est pas une date valide au format AAAAMMJJ."
            )


@register
class SeparatorRule(FileRule):
    """Fields must be separated by tabs or pipes."""

    code = "FEC-F004"
    severity = Severity.ERROR
    title = "Séparateur de champs non reconnu"
    fatal = True

    def check(self, ctx: FileContext) -> Iterator[Issue]:
        if ctx.separator is None:
            yield self.issue(
                "Aucun séparateur reconnu dans la ligne d'en-tête : la tabulation ou la "
                "barre verticale (|) est attendue. Les lignes ne sont pas analysées.",
                line=1,
            )


@register
class MissingColumnsRule(FileRule):
    """Every expected column must be present in the header."""

    code = "FEC-F005"
    severity = Severity.ERROR
    title = "Colonnes obligatoires absentes de l'en-tête"
    fatal = True

    def check(self, ctx: FileContext) -> Iterator[Issue]:
        if ctx.separator is not None and ctx.header.missing:
            yield self.issue(
                "Colonnes absentes de l'en-tête : "
                + ", ".join(ctx.header.missing)
                + ". Les lignes ne sont pas analysées.",
                line=1,
            )


@register
class UnexpectedColumnsRule(FileRule):
    """No column other than the 18 of the norm, and no duplicate."""

    code = "FEC-F006"
    severity = Severity.ERROR
    title = "Colonnes inattendues ou en double"

    def check(self, ctx: FileContext) -> Iterator[Issue]:
        if ctx.separator is not None and ctx.header.unexpected:
            yield self.issue(
                "Colonnes inattendues ou en double dans l'en-tête : "
                + ", ".join(repr(name) for name in ctx.header.unexpected)
                + ".",
                line=1,
            )


@register
class ColumnOrderRule(FileRule):
    """Columns must appear in the order of the norm."""

    code = "FEC-F007"
    severity = Severity.ERROR
    title = "Ordre des colonnes non conforme"

    def check(self, ctx: FileContext) -> Iterator[Issue]:
        header = ctx.header
        if ctx.separator is not None and header.usable and not header.order_ok:
            yield self.issue(
                "Les colonnes ne sont pas dans l'ordre réglementaire : "
                + ", ".join(header.expected)
                + ".",
                line=1,
            )


@register
class ColumnCaseRule(FileRule):
    """Column names should be written exactly as in the norm."""

    code = "FEC-F008"
    severity = Severity.WARNING
    title = "Casse des noms de colonnes différente de la norme"

    def check(self, ctx: FileContext) -> Iterator[Issue]:
        if ctx.separator is None:
            return
        for found, expected in ctx.header.case_mismatches:
            yield self.issue(
                f"Colonne '{found}' : la norme l'écrit '{expected}'.", line=1, column=expected
            )
