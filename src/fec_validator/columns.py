"""Column definitions of the FEC (article A47 A-1 du LPF)."""

from __future__ import annotations

import enum


class Layout(enum.StrEnum):
    """The two column layouts allowed for amounts."""

    DEBIT_CREDIT = "debit_credit"
    MONTANT_SENS = "montant_sens"

    @property
    def label(self) -> str:
        """French label used in human readable reports."""
        return "Debit / Credit" if self is Layout.DEBIT_CREDIT else "Montant / Sens"


DEBIT_CREDIT_COLUMNS: tuple[str, ...] = (
    "JournalCode",
    "JournalLib",
    "EcritureNum",
    "EcritureDate",
    "CompteNum",
    "CompteLib",
    "CompAuxNum",
    "CompAuxLib",
    "PieceRef",
    "PieceDate",
    "EcritureLib",
    "Debit",
    "Credit",
    "EcritureLet",
    "DateLet",
    "ValidDate",
    "Montantdevise",
    "Idevise",
)

MONTANT_SENS_COLUMNS: tuple[str, ...] = (
    *DEBIT_CREDIT_COLUMNS[:11],
    "Montant",
    "Sens",
    *DEBIT_CREDIT_COLUMNS[13:],
)

COLUMNS_BY_LAYOUT: dict[Layout, tuple[str, ...]] = {
    Layout.DEBIT_CREDIT: DEBIT_CREDIT_COLUMNS,
    Layout.MONTANT_SENS: MONTANT_SENS_COLUMNS,
}

MANDATORY_COLUMNS: tuple[str, ...] = (
    "JournalCode",
    "JournalLib",
    "EcritureNum",
    "EcritureDate",
    "CompteNum",
    "CompteLib",
    "PieceRef",
    "PieceDate",
    "EcritureLib",
    "ValidDate",
)

# Dates that must always be present (their emptiness is reported by the
# mandatory field rule) and dates that are only checked when filled.
REQUIRED_DATE_COLUMNS: tuple[str, ...] = ("EcritureDate", "PieceDate", "ValidDate")
OPTIONAL_DATE_COLUMNS: tuple[str, ...] = ("DateLet",)

AMOUNT_COLUMNS_BY_LAYOUT: dict[Layout, tuple[str, ...]] = {
    Layout.DEBIT_CREDIT: ("Debit", "Credit", "Montantdevise"),
    Layout.MONTANT_SENS: ("Montant", "Montantdevise"),
}
