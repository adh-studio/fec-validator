from datetime import date
from decimal import Decimal

import pytest

from fec_validator.columns import Layout
from fec_validator.parsing import (
    amount_hint,
    debit_credit,
    format_amount_fr,
    format_date_fr,
    parse_amount,
    parse_date,
    parse_sens,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("20250115", date(2025, 1, 15)),
        ("20240229", date(2024, 2, 29)),
        ("20250229", None),
        ("20251301", None),
        ("2025-01-15", None),
        ("15012025", None),
        ("2025011", None),
        ("", None),
    ],
)
def test_parse_date(text: str, expected: date | None) -> None:
    assert parse_date(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1234,56", Decimal("1234.56")),
        ("0,00", Decimal("0.00")),
        ("12", Decimal("12")),
        ("-12,5", Decimal("-12.5")),
        ("+3,10", Decimal("3.10")),
        ("0,001", Decimal("0.001")),
        ("", Decimal(0)),
        ("1234.56", None),
        ("1 234,56", None),
        ("1\u00a0234,56", None),
        (",50", None),
        ("12,", None),
        ("abc", None),
    ],
)
def test_parse_amount(text: str, expected: Decimal | None) -> None:
    assert parse_amount(text) == expected


def test_parse_amount_is_exact_decimal() -> None:
    total = sum((parse_amount("0,10") or Decimal(0) for _ in range(3)), Decimal(0))
    assert total == Decimal("0.30")


@pytest.mark.parametrize(
    ("text", "expected"),
    [("D", 1), ("d", 1), ("+1", 1), ("1", 1), ("C", -1), ("c", -1), ("-1", -1), ("X", None)],
)
def test_parse_sens(text: str, expected: int | None) -> None:
    assert parse_sens(text) == expected


def test_amount_hint_messages() -> None:
    assert "milliers" in amount_hint("1 234,56")
    assert "milliers" in amount_hint("1\u202f234,56")
    assert "virgule" in amount_hint("12.50")
    assert "format attendu" in amount_hint("abc")


def test_debit_credit_both_layouts() -> None:
    assert debit_credit({"Debit": "10,00", "Credit": "0,00"}, Layout.DEBIT_CREDIT) == (
        Decimal("10.00"),
        Decimal("0.00"),
    )
    assert debit_credit({"Debit": "10.00", "Credit": ""}, Layout.DEBIT_CREDIT) is None
    assert debit_credit({"Montant": "5,00", "Sens": "D"}, Layout.MONTANT_SENS) == (
        Decimal("5.00"),
        Decimal(0),
    )
    assert debit_credit({"Montant": "5,00", "Sens": "-1"}, Layout.MONTANT_SENS) == (
        Decimal(0),
        Decimal("5.00"),
    )
    assert debit_credit({"Montant": "5,00", "Sens": "?"}, Layout.MONTANT_SENS) is None
    assert debit_credit({"Montant": "5.00", "Sens": "D"}, Layout.MONTANT_SENS) is None


@pytest.mark.parametrize(
    ("value", "grouping", "expected"),
    [
        (Decimal("1234.5"), False, "1234,50"),
        (Decimal("1234.5"), True, "1 234,50"),
        (Decimal("-1234567"), True, "-1 234 567,00"),
        (Decimal("0.001"), False, "0,001"),
        (Decimal(0), False, "0,00"),
    ],
)
def test_format_amount_fr(value: Decimal, grouping: bool, expected: str) -> None:
    assert format_amount_fr(value, grouping=grouping) == expected


def test_format_date_fr() -> None:
    assert format_date_fr(date(2025, 12, 31)) == "31/12/2025"
    assert format_date_fr(None) == ""
