"""Builders for small synthetic FEC files. All data is fake."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path

from fec_validator.columns import DEBIT_CREDIT_COLUMNS, MONTANT_SENS_COLUMNS, Layout
from fec_validator.context import ValidationContext
from fec_validator.models import FecLine, FiscalPeriod

# Fake SIREN numbers: the first passes the Luhn check, the second does not.
VALID_SIREN = "123456782"
INVALID_SIREN = "123456789"
VALID_NAME = f"{VALID_SIREN}FEC20251231.txt"

PERIOD_2025 = FiscalPeriod(start=date(2025, 1, 1), end=date(2025, 12, 31))

Row = dict[str, str]


def make_row(**overrides: str) -> Row:
    """A valid line (debit and credit both zero until overridden)."""
    row = {
        "JournalCode": "VT",
        "JournalLib": "Ventes",
        "EcritureNum": "VT0001",
        "EcritureDate": "20250115",
        "CompteNum": "41100000",
        "CompteLib": "Clients",
        "CompAuxNum": "",
        "CompAuxLib": "",
        "PieceRef": "F2025-001",
        "PieceDate": "20250115",
        "EcritureLib": "Facture client",
        "Debit": "0,00",
        "Credit": "0,00",
        "EcritureLet": "",
        "DateLet": "",
        "ValidDate": "20250120",
        "Montantdevise": "",
        "Idevise": "",
    }
    row.update(overrides)
    return row


def valid_rows() -> list[Row]:
    """Four balanced entries covering auxiliary accounts, lettering and currency."""
    return [
        make_row(
            CompteNum="41100000",
            CompteLib="Clients",
            CompAuxNum="CLI001",
            CompAuxLib="Client Alpha",
            Debit="1200,00",
            EcritureLet="A",
            DateLet="20250210",
        ),
        make_row(CompteNum="70600000", CompteLib="Prestations de services", Credit="1000,00"),
        make_row(CompteNum="44571000", CompteLib="TVA collectée", Credit="200,00"),
        make_row(
            JournalCode="AC",
            JournalLib="Achats",
            EcritureNum="AC0001",
            EcritureDate="20250120",
            CompteNum="60610000",
            CompteLib="Fournitures non stockables",
            PieceRef="FA-778",
            PieceDate="20250118",
            EcritureLib="Facture fournisseur",
            Debit="100,00",
            ValidDate="20250121",
        ),
        make_row(
            JournalCode="AC",
            JournalLib="Achats",
            EcritureNum="AC0001",
            EcritureDate="20250120",
            CompteNum="44566000",
            CompteLib="TVA déductible",
            PieceRef="FA-778",
            PieceDate="20250118",
            EcritureLib="Facture fournisseur",
            Debit="20,00",
            ValidDate="20250121",
        ),
        make_row(
            JournalCode="AC",
            JournalLib="Achats",
            EcritureNum="AC0001",
            EcritureDate="20250120",
            CompteNum="40100000",
            CompteLib="Fournisseurs",
            CompAuxNum="FRS001",
            CompAuxLib="Fournisseur Beta",
            PieceRef="FA-778",
            PieceDate="20250118",
            EcritureLib="Facture fournisseur",
            Credit="120,00",
            ValidDate="20250121",
        ),
        make_row(
            JournalCode="BQ",
            JournalLib="Banque",
            EcritureNum="BQ0001",
            EcritureDate="20250210",
            CompteNum="51200000",
            CompteLib="Banque",
            PieceRef="RLV-02",
            PieceDate="20250210",
            EcritureLib="Règlement client",
            Debit="1200,00",
            ValidDate="20250211",
        ),
        make_row(
            JournalCode="BQ",
            JournalLib="Banque",
            EcritureNum="BQ0001",
            EcritureDate="20250210",
            CompteNum="41100000",
            CompteLib="Clients",
            CompAuxNum="CLI001",
            CompAuxLib="Client Alpha",
            PieceRef="RLV-02",
            PieceDate="20250210",
            EcritureLib="Règlement client",
            Credit="1200,00",
            EcritureLet="A",
            DateLet="20250210",
            ValidDate="20250211",
        ),
        make_row(
            JournalCode="AC",
            JournalLib="Achats",
            EcritureNum="AC0002",
            EcritureDate="20250305",
            CompteNum="60400000",
            CompteLib="Achats de prestations",
            PieceRef="INV-55",
            PieceDate="20250301",
            EcritureLib="Facture en dollars",
            Debit="92,00",
            ValidDate="20250306",
            Montantdevise="100,00",
            Idevise="USD",
        ),
        make_row(
            JournalCode="AC",
            JournalLib="Achats",
            EcritureNum="AC0002",
            EcritureDate="20250305",
            CompteNum="40100000",
            CompteLib="Fournisseurs",
            CompAuxNum="FRS002",
            CompAuxLib="Supplier Gamma",
            PieceRef="INV-55",
            PieceDate="20250301",
            EcritureLib="Facture en dollars",
            Credit="92,00",
            ValidDate="20250306",
            Montantdevise="-100,00",
            Idevise="USD",
        ),
    ]


def to_montant_sens(row: Row, *, numeric_sens: bool = False) -> Row:
    """Convert a Debit/Credit row to the Montant/Sens layout."""
    converted = {key: value for key, value in row.items() if key not in ("Debit", "Credit")}
    debit = row.get("Debit", "")
    if debit and debit not in ("0", "0,00"):
        converted["Montant"] = debit
        converted["Sens"] = "+1" if numeric_sens else "D"
    else:
        converted["Montant"] = row.get("Credit", "")
        converted["Sens"] = "-1" if numeric_sens else "C"
    return converted


def render_fec(
    rows: Iterable[Row],
    *,
    separator: str = "\t",
    columns: Sequence[str] = DEBIT_CREDIT_COLUMNS,
    header: Sequence[str] | None = None,
    newline: str = "\r\n",
) -> str:
    """Render rows as FEC text."""
    lines = [separator.join(header if header is not None else columns)]
    lines.extend(separator.join(row.get(column, "") for column in columns) for row in rows)
    return newline.join(lines) + newline


def write_fec(
    directory: Path,
    rows: Iterable[Row],
    *,
    name: str = VALID_NAME,
    separator: str = "\t",
    encoding: str = "utf-8",
    layout: Layout = Layout.DEBIT_CREDIT,
    header: Sequence[str] | None = None,
    newline: str = "\r\n",
) -> Path:
    """Write a FEC file and return its path. ``encoding='utf-8-sig'`` adds a BOM."""
    columns = DEBIT_CREDIT_COLUMNS if layout is Layout.DEBIT_CREDIT else MONTANT_SENS_COLUMNS
    text = render_fec(rows, separator=separator, columns=columns, header=header, newline=newline)
    path = directory / name
    path.write_bytes(text.encode(encoding))
    return path


def make_line(number: int = 2, **overrides: str) -> FecLine:
    """A parsed line for unit tests of line rules."""
    fields = make_row(**overrides)
    return FecLine(number, fields, len(fields))


def make_sens_line(number: int = 2, **overrides: str) -> FecLine:
    """A parsed Montant/Sens line for unit tests of line rules."""
    fields = to_montant_sens(make_row())
    fields.update(overrides)
    return FecLine(number, fields, len(fields))


def context(
    period: FiscalPeriod = PERIOD_2025, layout: Layout = Layout.DEBIT_CREDIT
) -> ValidationContext:
    """A validation context for unit tests."""
    return ValidationContext(period=period, layout=layout)
