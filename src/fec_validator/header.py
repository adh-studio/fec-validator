"""Analysis of the header line: layout, missing, unexpected and misplaced columns."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fec_validator.columns import COLUMNS_BY_LAYOUT, Layout


@dataclass(frozen=True, slots=True)
class HeaderAnalysis:
    """Result of comparing the header with the expected columns.

    ``columns`` has one key per field of the file, in file order: the
    canonical column name when recognized, a unique placeholder otherwise.
    It is used to build the field dictionary of every line.
    """

    raw: tuple[str, ...]
    layout: Layout
    columns: tuple[str, ...]
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]
    order_ok: bool
    case_mismatches: tuple[tuple[str, str], ...]

    @property
    def expected(self) -> tuple[str, ...]:
        """Expected columns for the detected layout."""
        return COLUMNS_BY_LAYOUT[self.layout]

    @property
    def usable(self) -> bool:
        """True when every expected column is present, so lines can be checked."""
        return not self.missing


def detect_layout(names: Sequence[str]) -> Layout:
    """Guess the amount layout from the column names."""
    lowered = {name.lower() for name in names}
    if {"montant", "sens"} <= lowered and not {"debit", "credit"} & lowered:
        return Layout.MONTANT_SENS
    return Layout.DEBIT_CREDIT


def analyse_header(names: Sequence[str]) -> HeaderAnalysis:
    """Compare header ``names`` with the norm (case insensitive matching)."""
    layout = detect_layout(names)
    expected = COLUMNS_BY_LAYOUT[layout]
    canonical_by_lower = {column.lower(): column for column in expected}

    columns: list[str] = []
    recognized: list[str] = []
    unexpected: list[str] = []
    case_mismatches: list[tuple[str, str]] = []
    for index, name in enumerate(names):
        canonical = canonical_by_lower.get(name.lower())
        if canonical is None or canonical in recognized:
            unexpected.append(name)
            columns.append(f"#{index + 1}:{name}")
            continue
        if name != canonical:
            case_mismatches.append((name, canonical))
        recognized.append(canonical)
        columns.append(canonical)

    present = set(recognized)
    missing = tuple(column for column in expected if column not in present)
    order_ok = recognized == [column for column in expected if column in present]
    return HeaderAnalysis(
        raw=tuple(names),
        layout=layout,
        columns=tuple(columns),
        missing=missing,
        unexpected=tuple(unexpected),
        order_ok=order_ok,
        case_mismatches=tuple(case_mismatches),
    )
