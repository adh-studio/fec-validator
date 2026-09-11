"""Human (rich) and machine (JSON) renderings of reports."""

from __future__ import annotations

import json

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from fec_validator.balance import BalanceResult
from fec_validator.models import Severity
from fec_validator.parsing import format_amount_fr, format_date_fr
from fec_validator.reader import ENCODING_LABELS, SEPARATOR_LABELS
from fec_validator.report import ValidationReport
from fec_validator.rules import get_rule

_SEVERITY_STYLES = {Severity.ERROR: "bold red", Severity.WARNING: "yellow"}


def render_json(report: ValidationReport) -> str:
    """Return the report as an indented JSON document."""
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)


def _describe_siren(report: ValidationReport) -> str:
    info = report.filename
    if info is None:
        return "non déterminé (nom de fichier non conforme)"
    key = "valide" if info.siren_valid else "invalide"
    return f"{info.siren} (clé de contrôle {key})"


def _describe_period(report: ValidationReport) -> str:
    period = report.period
    if not period.is_known:
        return "inconnu (préciser --debut et --fin)"
    start = format_date_fr(period.start) or "?"
    end = format_date_fr(period.end) or "?"
    text = f"du {start} au {end}"
    if period.start_inferred:
        text += " (début supposé : exercice de 12 mois)"
    return text


def _metadata_table(report: ValidationReport) -> Table:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    info = report.filename
    closing = format_date_fr(info.closing_date) if info and info.closing_date else "inconnue"
    totals = report.totals
    rows = [
        ("SIREN", _describe_siren(report)),
        ("Date de clôture", closing),
        ("Exercice", _describe_period(report)),
        ("Encodage", ENCODING_LABELS.get(report.encoding, report.encoding)),
        ("Séparateur", SEPARATOR_LABELS.get(report.separator or "", "non reconnu")),
        ("Format des montants", report.layout.label if report.layout else "non déterminé"),
        ("Lignes analysées", f"{totals.line_count:,}".replace(",", " ")),
        ("Écritures", f"{totals.entry_count:,}".replace(",", " ")),
        ("Total débit", format_amount_fr(totals.debit, grouping=True)),
        ("Total crédit", format_amount_fr(totals.credit, grouping=True)),
        ("Durée", f"{report.duration_seconds:.2f} s".replace(".", ",")),
    ]
    for key, value in rows:
        grid.add_row(key, Text(value))
    return grid


def _summary_table(report: ValidationReport) -> Table:
    table = Table(title="Anomalies par règle", box=box.SIMPLE_HEAVY, title_justify="left")
    table.add_column("Code", no_wrap=True)
    table.add_column("Gravité", no_wrap=True)
    table.add_column("Règle")
    table.add_column("Nombre", justify="right")
    for code in sorted(report.counts):
        rule = get_rule(code)
        severity = rule.severity if rule else Severity.ERROR
        title = rule.title if rule else ""
        table.add_row(
            code,
            Text(severity.label, style=_SEVERITY_STYLES[severity]),
            Text(title),
            str(report.counts[code]),
        )
    return table


def _detail_table(report: ValidationReport) -> Table:
    table = Table(title="Détail", box=box.SIMPLE_HEAVY, title_justify="left")
    table.add_column("Ligne", justify="right", no_wrap=True)
    table.add_column("Code", no_wrap=True)
    table.add_column("Message")
    for issue in report.issues:
        table.add_row(
            str(issue.line) if issue.line is not None else "",
            Text(issue.code, style=_SEVERITY_STYLES[issue.severity]),
            Text(issue.message),
        )
    return table


def render_console(report: ValidationReport, console: Console) -> None:
    """Print a human readable report."""
    console.print(
        Panel(
            _metadata_table(report),
            title=Text(f"Validation FEC : {report.path.name}", style="bold"),
            title_align="left",
            box=box.ROUNDED,
            expand=False,
        )
    )
    if report.counts:
        console.print(_summary_table(report))
        console.print(_detail_table(report))
        if report.truncated:
            console.print(
                Text(
                    f"Seules les {report.max_issues_per_rule} premières anomalies de chaque "
                    "règle sont détaillées (option --max-anomalies).",
                    style="dim",
                )
            )
    if report.fatal:
        console.print(
            Text("Analyse interrompue : l'en-tête du fichier est inexploitable.", style="bold red")
        )
    verdict = (
        Text("FICHIER CONFORME", style="bold green")
        if report.is_valid
        else Text("FICHIER NON CONFORME", style="bold red")
    )
    counts = f" : {report.error_count} erreur(s), {report.warning_count} avertissement(s)"
    console.print(Text.assemble(verdict, counts))


def render_balance(result: BalanceResult, console: Console) -> None:
    """Print the balance générale as a table."""
    table = Table(title="Balance générale", box=box.SIMPLE_HEAVY, title_justify="left")
    table.add_column("CompteNum", no_wrap=True)
    table.add_column("CompteLib")
    table.add_column("Débit", justify="right", no_wrap=True)
    table.add_column("Crédit", justify="right", no_wrap=True)
    table.add_column("Solde", justify="right", no_wrap=True)
    for account in result.accounts:
        table.add_row(
            account.compte_num,
            Text(account.compte_lib),
            format_amount_fr(account.debit, grouping=True),
            format_amount_fr(account.credit, grouping=True),
            format_amount_fr(account.solde, grouping=True),
        )
    table.add_section()
    table.add_row(
        Text("Total", style="bold"),
        "",
        format_amount_fr(result.total_debit, grouping=True),
        format_amount_fr(result.total_credit, grouping=True),
        format_amount_fr(result.total_debit - result.total_credit, grouping=True),
    )
    console.print(table)
    render_balance_footer(result, console)


def render_balance_footer(result: BalanceResult, console: Console) -> None:
    """Print the counters of a balance computation."""
    console.print(
        f"{len(result.accounts)} comptes, {result.line_count} lignes lues", highlight=False
    )
    if result.skipped_lines:
        console.print(
            Text(
                f"{result.skipped_lines} ligne(s) ignorée(s) (montant illisible ou nombre de "
                "champs incorrect) : lancer 'fec-check validate' pour le détail.",
                style="yellow",
            )
        )
