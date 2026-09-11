"""Command line interface: ``fec-check``."""

from __future__ import annotations

import enum
import io
import sys
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from fec_validator import __version__
from fec_validator.balance import compute_balance, write_balance_csv
from fec_validator.errors import FecReadError
from fec_validator.parsing import parse_date
from fec_validator.renderers import (
    render_balance,
    render_balance_footer,
    render_console,
    render_json,
)
from fec_validator.report import DEFAULT_MAX_ISSUES_PER_RULE
from fec_validator.rules import registered_rules
from fec_validator.validator import validate

EXIT_UNREADABLE = 2
"""Exit code when the file cannot be read (0 and 1 come from ``ValidationReport.exit_code``)."""

app = typer.Typer(
    name="fec-check",
    help="Contrôle d'un Fichier des Écritures Comptables (FEC) et export de la balance générale.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
)


class OutputFormat(enum.StrEnum):
    """Report formats of the validate command."""

    CONSOLE = "console"
    JSON = "json"


def _parse_cli_date(value: str | None, option: str) -> date | None:
    if value is None:
        return None
    parsed = parse_date(value.replace("-", ""))
    if parsed is None:
        raise typer.BadParameter(
            f"date invalide '{value}' (formats acceptés : AAAAMMJJ ou AAAA-MM-JJ)",
            param_hint=option,
        )
    return parsed


def _fail_unreadable(error: FecReadError) -> typer.Exit:
    Console(stderr=True).print(Text(f"Erreur : {error}", style="bold red"))
    return typer.Exit(EXIT_UNREADABLE)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"fec-check {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Affiche la version."
        ),
    ] = False,
) -> None:
    """Contrôle d'un Fichier des Écritures Comptables (FEC) et export de la balance générale."""


@app.command("validate")
def validate_command(
    fichier: Annotated[Path, typer.Argument(help="Fichier FEC à contrôler.", show_default=False)],
    debut: Annotated[
        str | None,
        typer.Option(
            "--debut", help="Début de l'exercice (AAAAMMJJ). Par défaut : clôture - 12 mois."
        ),
    ] = None,
    fin: Annotated[
        str | None,
        typer.Option(
            "--fin", help="Clôture de l'exercice (AAAAMMJJ). Par défaut : nom du fichier."
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Format du rapport.")
    ] = OutputFormat.CONSOLE,
    max_anomalies: Annotated[
        int,
        typer.Option(
            "--max-anomalies",
            min=1,
            help="Nombre d'anomalies détaillées par règle (toutes sont comptées).",
        ),
    ] = DEFAULT_MAX_ISSUES_PER_RULE,
    ignorer: Annotated[
        list[str] | None,
        typer.Option("--ignorer", help="Code de règle à désactiver (option répétable)."),
    ] = None,
    strict: Annotated[
        bool, typer.Option("--strict", help="Code retour 1 aussi en cas d'avertissement.")
    ] = False,
) -> None:
    """Contrôle un FEC. Code retour : 0 conforme, 1 anomalies bloquantes, 2 fichier illisible."""
    start = _parse_cli_date(debut, "--debut")
    end = _parse_cli_date(fin, "--fin")
    if start is not None and end is not None and start > end:
        raise typer.BadParameter(
            "le début de l'exercice est postérieur à sa fin", param_hint="--debut"
        )
    try:
        report = validate(
            fichier,
            start=start,
            end=end,
            max_issues_per_rule=max_anomalies,
            exclude=ignorer or (),
        )
    except FecReadError as error:
        raise _fail_unreadable(error) from error
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="--ignorer") from error

    if output_format is OutputFormat.JSON:
        typer.echo(render_json(report))
    else:
        render_console(report, Console())
    raise typer.Exit(report.exit_code(strict=strict))


@app.command("balance")
def balance_command(
    fichier: Annotated[Path, typer.Argument(help="Fichier FEC.", show_default=False)],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Fichier CSV à écrire (séparateur ';'). Sans cette option : affichage.",
        ),
    ] = None,
) -> None:
    """Calcule la balance générale par CompteNum (total débit, total crédit, solde)."""
    try:
        result = compute_balance(fichier)
    except FecReadError as error:
        raise _fail_unreadable(error) from error

    console = Console()
    if output is None:
        render_balance(result, console)
        return
    try:
        with output.open("w", encoding="utf-8-sig", newline="") as handle:
            write_balance_csv(result, handle)
    except OSError as error:
        Console(stderr=True).print(
            Text(f"Erreur : impossible d'écrire {output} ({error.strerror}).", style="bold red")
        )
        raise typer.Exit(EXIT_UNREADABLE) from error
    console.print(f"Balance générale écrite dans {output}", highlight=False, soft_wrap=True)
    render_balance_footer(result, console)


@app.command("rules")
def rules_command() -> None:
    """Liste les règles de contrôle disponibles."""
    table = Table(box=box.SIMPLE_HEAVY)
    table.add_column("Code", no_wrap=True)
    table.add_column("Gravité", no_wrap=True)
    table.add_column("Portée", no_wrap=True)
    table.add_column("Règle")
    for rule in registered_rules():
        table.add_row(rule.code, rule.severity.label, rule.scope.label, Text(rule.title))
    Console().print(table)


def _make_output_safe() -> None:
    """Avoid crashes when a redirected stream cannot encode a character.

    On Windows, a redirected standard output uses the ANSI code page, which
    cannot encode every character. Unencodable characters are replaced
    instead of raising ``UnicodeEncodeError``.
    """
    for stream in (sys.stdout, sys.stderr):
        if (
            isinstance(stream, io.TextIOWrapper)
            and stream.encoding.lower().replace("-", "") != "utf8"
        ):
            stream.reconfigure(errors="replace")


def main() -> None:
    """Entry point of the ``fec-check`` script."""
    _make_output_safe()
    app()
