"""Parsing of FEC field values: dates, amounts and debit/credit direction.

Values repeat a lot in a FEC (the same dates, ``0,00`` on every other line),
so the parsers are memoized with a bounded cache.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from functools import lru_cache

from fec_validator.columns import Layout

ZERO = Decimal(0)

_DATE_RE = re.compile(r"\d{8}")
_AMOUNT_RE = re.compile(r"[+-]?\d+(?:,\d+)?")
_DEBIT_SENS = frozenset({"D", "+1", "1"})
_CREDIT_SENS = frozenset({"C", "-1"})
# Regular, non-breaking and narrow non-breaking spaces, all used as thousands separators.
_THOUSANDS_RE = re.compile(r"\d[ \u00a0\u202f.]\d{3}(?:\D|$)")


@lru_cache(maxsize=8192)
def parse_date(text: str) -> date | None:
    """Parse an ``AAAAMMJJ`` date. Return ``None`` if the format or the date is invalid."""
    if _DATE_RE.fullmatch(text) is None:
        return None
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


@lru_cache(maxsize=8192)
def parse_amount(text: str) -> Decimal | None:
    """Parse a FEC amount (comma decimal separator, no thousands separator).

    An empty value means zero. Return ``None`` when the format is invalid.
    """
    if not text:
        return ZERO
    if _AMOUNT_RE.fullmatch(text) is None:
        return None
    return Decimal(text.replace(",", "."))


def parse_sens(text: str) -> int | None:
    """Parse the ``Sens`` column: ``+1`` for debit, ``-1`` for credit, ``None`` if invalid.

    The norm uses ``D``/``C``; ``+1``/``-1`` (and ``1``) are also seen in practice.
    """
    value = text.upper()
    if value in _DEBIT_SENS:
        return 1
    if value in _CREDIT_SENS:
        return -1
    return None


def amount_hint(text: str) -> str:
    """Explain in French why ``text`` is not a valid amount."""
    if _THOUSANDS_RE.search(text):
        return "les séparateurs de milliers sont interdits"
    if "." in text:
        return "le séparateur décimal doit être la virgule"
    return "format attendu : chiffres avec une virgule décimale, par exemple 1234,56"


def debit_credit(fields: dict[str, str], layout: Layout) -> tuple[Decimal, Decimal] | None:
    """Return ``(debit, credit)`` for a line, whatever the layout.

    Return ``None`` when the amount (or the direction) cannot be parsed.
    """
    if layout is Layout.DEBIT_CREDIT:
        debit = parse_amount(fields.get("Debit", ""))
        credit = parse_amount(fields.get("Credit", ""))
        if debit is None or credit is None:
            return None
        return debit, credit
    amount = parse_amount(fields.get("Montant", ""))
    sens = parse_sens(fields.get("Sens", ""))
    if amount is None or sens is None:
        return None
    return (amount, ZERO) if sens > 0 else (ZERO, amount)


def format_amount_fr(value: Decimal, *, grouping: bool = False) -> str:
    """Format an amount the French way: ``1234,50`` or ``1 234,50`` with grouping.

    At least two decimals are shown; more are kept when present so that no
    precision is silently lost.
    """
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent > -2:
        value = value.quantize(Decimal("0.01"))
    text = f"{value:,f}" if grouping else f"{value:f}"
    return text.replace(",", " ").replace(".", ",")


def format_date_fr(value: date | None) -> str:
    """Format a date as ``JJ/MM/AAAA`` (empty string for ``None``)."""
    return value.strftime("%d/%m/%Y") if value else ""
