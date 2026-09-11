from datetime import date

import pytest

from fec_validator.filename import luhn_valid, parse_filename, previous_closing, resolve_period
from fec_validator.models import FiscalPeriod


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        ("123456782", True),
        ("123456789", False),
        ("000000000", True),
        ("356000000", True),
        ("12345678A", False),
        ("", False),
    ],
)
def test_luhn(number: str, expected: bool) -> None:
    assert luhn_valid(number) is expected


def test_parse_filename_valid() -> None:
    info = parse_filename("123456782FEC20251231.txt")
    assert info is not None
    assert info.siren == "123456782"
    assert info.closing_date == date(2025, 12, 31)
    assert info.siren_valid


@pytest.mark.parametrize("name", ["123456782fec20251231.csv", "123456782FEC20251231"])
def test_parse_filename_variants(name: str) -> None:
    info = parse_filename(name)
    assert info is not None
    assert info.closing_date == date(2025, 12, 31)


@pytest.mark.parametrize(
    "name", ["export.txt", "12345678FEC20251231.txt", "123456782FEC2025123.txt", "FEC.txt"]
)
def test_parse_filename_non_conforming(name: str) -> None:
    assert parse_filename(name) is None


def test_parse_filename_invalid_date_and_siren() -> None:
    info = parse_filename("123456789FEC20251332.txt")
    assert info is not None
    assert info.closing_date is None
    assert info.closing_raw == "20251332"
    assert not info.siren_valid


@pytest.mark.parametrize(
    ("end", "expected"),
    [
        (date(2025, 12, 31), date(2024, 12, 31)),
        (date(2025, 6, 30), date(2024, 6, 30)),
        (date(2025, 2, 28), date(2024, 2, 29)),
        (date(2024, 2, 29), date(2023, 2, 28)),
        (date(2025, 3, 15), date(2024, 3, 15)),
    ],
)
def test_previous_closing(end: date, expected: date) -> None:
    assert previous_closing(end) == expected


def test_resolve_period_from_filename() -> None:
    info = parse_filename("123456782FEC20250630.txt")
    assert resolve_period(info) == FiscalPeriod(date(2024, 7, 1), date(2025, 6, 30), True)


def test_resolve_period_explicit_bounds_win() -> None:
    info = parse_filename("123456782FEC20251231.txt")
    period = resolve_period(info, start=date(2024, 7, 1), end=date(2025, 12, 31))
    assert period == FiscalPeriod(date(2024, 7, 1), date(2025, 12, 31), False)


def test_resolve_period_unknown() -> None:
    period = resolve_period(None)
    assert not period.is_known
    assert resolve_period(None, start=date(2025, 1, 1)).is_known


def test_resolve_period_explicit_end_without_name() -> None:
    period = resolve_period(None, end=date(2025, 12, 31))
    assert period.start == date(2025, 1, 1)
    assert period.start_inferred
