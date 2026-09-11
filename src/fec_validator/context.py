"""Read-only contexts handed to rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fec_validator.columns import Layout
from fec_validator.filename import FileNameInfo
from fec_validator.header import HeaderAnalysis
from fec_validator.models import FiscalPeriod


@dataclass(frozen=True, slots=True)
class FileContext:
    """Everything known about the file before reading its data lines."""

    path: Path
    filename: FileNameInfo | None
    encoding: str
    separator: str | None
    header: HeaderAnalysis


@dataclass(frozen=True, slots=True)
class ValidationContext:
    """Information shared by line, entry and global rules."""

    period: FiscalPeriod
    layout: Layout = Layout.DEBIT_CREDIT
    column_count: int = 18
    """Number of columns declared by the header, i.e. fields expected on each line."""
