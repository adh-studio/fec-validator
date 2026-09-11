"""End to end tests of the library on synthetic files."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from fec_factory import (
    INVALID_SIREN,
    make_row,
    render_fec,
    to_montant_sens,
    valid_rows,
    write_fec,
)
from fec_validator import FecReadError, validate
from fec_validator.columns import DEBIT_CREDIT_COLUMNS, Layout
from fec_validator.rules import RuleSet


@pytest.mark.parametrize("separator", ["\t", "|"])
@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1252", "iso-8859-15"])
def test_valid_file_all_separators_and_encodings(
    tmp_path: Path, separator: str, encoding: str
) -> None:
    report = validate(write_fec(tmp_path, valid_rows(), separator=separator, encoding=encoding))
    assert report.issues == []
    assert report.is_valid
    assert report.encoding == ("iso-8859-15" if encoding == "cp1252" else encoding)
    assert report.separator == separator
    assert report.totals.line_count == 10
    assert report.totals.entry_count == 4
    assert report.totals.debit == report.totals.credit == Decimal("2612.00")


def test_cp1252_is_detected_with_euro_sign(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[0]["EcritureLib"] = "Facture 1200 €"
    report = validate(write_fec(tmp_path, rows, encoding="cp1252"))
    assert report.encoding == "cp1252"
    assert report.is_valid


@pytest.mark.parametrize("numeric_sens", [False, True])
def test_valid_montant_sens_file(tmp_path: Path, numeric_sens: bool) -> None:
    rows = [to_montant_sens(row, numeric_sens=numeric_sens) for row in valid_rows()]
    report = validate(write_fec(tmp_path, rows, layout=Layout.MONTANT_SENS))
    assert report.issues == []
    assert report.layout is Layout.MONTANT_SENS
    assert report.totals.debit == Decimal("2612.00")


def test_montant_sens_file_with_errors(tmp_path: Path) -> None:
    rows = [to_montant_sens(row) for row in valid_rows()]
    rows[1]["Sens"] = "X"
    rows[2]["Montant"] = "200.00"
    report = validate(write_fec(tmp_path, rows, layout=Layout.MONTANT_SENS))
    # Unreadable lines are left out of the totals, hence the global imbalance.
    assert report.counts == {"FEC-L006": 1, "FEC-L004": 1, "FEC-G001": 1}


def test_lf_line_endings(tmp_path: Path) -> None:
    assert validate(write_fec(tmp_path, valid_rows(), newline="\n")).is_valid


def _codes(tmp_path: Path, rows: list[dict[str, str]], **kwargs: object) -> dict[str, int]:
    return validate(write_fec(tmp_path, rows), **kwargs).counts  # type: ignore[arg-type]


def test_every_line_error_is_detected(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[0]["CompteLib"] = ""  # L002
    rows[1]["PieceDate"] = "20250230"  # L003
    rows[3]["Debit"] = "100.00"  # L004 (the entry balance is not checked)
    rows[6]["Credit"] = "1200,00"  # L005 + E001 on BQ0001
    rows[8]["EcritureLet"] = "B"  # L008 (no DateLet)
    rows[9]["CompAuxLib"] = ""  # L009
    counts = _codes(tmp_path, rows)
    assert counts == {
        "FEC-L002": 1,
        "FEC-L003": 1,
        "FEC-L004": 1,
        "FEC-L005": 1,
        "FEC-E001": 1,
        "FEC-L008": 1,
        "FEC-L009": 1,
        "FEC-G001": 1,
    }


def test_entry_and_period_errors(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[2]["Credit"] = "150,00"  # VT0001 unbalanced by 50
    rows[7]["EcritureDate"] = "20250211"  # BQ0001 has two dates
    rows.append(
        make_row(EcritureNum="VT0100", EcritureDate="20260103", ValidDate="20260104", Debit="10")
    )
    rows.append(
        make_row(EcritureNum="VT0100", EcritureDate="20260103", Credit="10,00", ValidDate="")
    )
    rows.append(
        make_row(EcritureNum="VT0101", EcritureDate="20250601", ValidDate="20250530", Debit="5")
    )
    rows.append(
        make_row(EcritureNum="VT0101", EcritureDate="20250601", ValidDate="20250602", Credit="5")
    )
    counts = _codes(tmp_path, rows)
    assert counts == {
        "FEC-E001": 1,
        "FEC-E002": 1,
        "FEC-G001": 1,
        "FEC-L002": 1,  # empty ValidDate
        "FEC-L012": 2,
        "FEC-L014": 1,
    }


def test_before_inferred_start_is_a_warning_and_debut_makes_it_an_error(tmp_path: Path) -> None:
    rows = valid_rows()
    for row in rows[:3]:
        row["EcritureDate"] = "20241231"
    path = write_fec(tmp_path, rows)
    inferred = validate(path)
    assert inferred.counts == {"FEC-L013": 3}
    assert inferred.is_valid
    explicit = validate(path, start=date(2025, 1, 1))
    assert explicit.counts == {"FEC-L012": 3}
    assert not explicit.is_valid
    longer_year = validate(path, start=date(2024, 12, 1))
    assert longer_year.counts == {}


def test_end_override_without_conforming_name(tmp_path: Path) -> None:
    path = write_fec(tmp_path, valid_rows(), name="export.txt")
    report = validate(path, end=date(2025, 2, 28))
    assert report.counts == {"FEC-F001": 1, "FEC-L012": 2}
    assert report.filename is None


def test_file_name_errors(tmp_path: Path) -> None:
    path = write_fec(tmp_path, valid_rows(), name=f"{INVALID_SIREN}FEC20251231.txt")
    assert validate(path).counts == {"FEC-F002": 1}
    path = write_fec(tmp_path, valid_rows(), name="123456782FEC20250229.txt")
    report = validate(path)
    assert report.counts == {"FEC-F003": 1}
    assert not report.period.is_known


def test_malformed_line_skips_other_line_checks(tmp_path: Path) -> None:
    rows = valid_rows()
    text = render_fec(rows)
    text += "VT\tVentes\tVT0099\t20250115\tbroken line\r\n"
    path = tmp_path / "123456782FEC20251231.txt"
    path.write_text(text, encoding="utf-8", newline="")
    report = validate(path)
    assert report.counts == {"FEC-L001": 1}
    assert report.totals.malformed_lines == 1
    assert report.totals.line_count == 11
    assert report.issues[0].line == 12


def test_fatal_header_stops_the_analysis(tmp_path: Path) -> None:
    path = write_fec(tmp_path, valid_rows(), header=DEBIT_CREDIT_COLUMNS[:17])
    report = validate(path)
    assert report.fatal
    assert report.counts == {"FEC-F005": 1}
    assert report.totals.line_count == 0
    assert report.layout is None
    assert report.exit_code() == 1


def test_unknown_separator_is_fatal(tmp_path: Path) -> None:
    path = write_fec(tmp_path, valid_rows(), separator=";")
    report = validate(path)
    assert report.fatal
    assert report.counts == {"FEC-F004": 1}


def test_fatal_even_if_the_fatal_rule_is_excluded(tmp_path: Path) -> None:
    path = write_fec(tmp_path, valid_rows(), separator=";")
    report = validate(path, exclude=["FEC-F004"])
    assert report.fatal
    assert report.counts == {}
    assert report.is_valid is True  # nothing reported, but nothing analysed either
    assert report.totals.line_count == 0


def test_header_warnings_do_not_stop_the_analysis(tmp_path: Path) -> None:
    header = [name.lower() for name in DEBIT_CREDIT_COLUMNS]
    report = validate(write_fec(tmp_path, valid_rows(), header=header))
    assert report.counts == {"FEC-F008": 18}
    assert report.totals.line_count == 10


def test_header_only_file(tmp_path: Path) -> None:
    report = validate(write_fec(tmp_path, []))
    assert report.counts == {"FEC-G002": 1}
    assert report.is_valid


def test_issue_cap_keeps_counting(tmp_path: Path) -> None:
    rows = [make_row(EcritureNum=f"VT{i:04d}", CompteLib="") for i in range(250)]
    report = validate(write_fec(tmp_path, rows), max_issues_per_rule=10)
    assert report.counts == {"FEC-L002": 250}
    assert len(report.issues) == 10
    assert report.truncated
    assert report.error_count == 250


def test_exclude_rules(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[0]["CompteLib"] = ""
    report = validate(write_fec(tmp_path, rows), exclude=["FEC-L002"])
    assert report.counts == {}


def test_explicit_ruleset(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[0]["CompteLib"] = ""
    empty = RuleSet((), (), (), ())
    assert validate(write_fec(tmp_path, rows), ruleset=empty).counts == {}


def test_unreadable_file(tmp_path: Path) -> None:
    with pytest.raises(FecReadError):
        validate(tmp_path / "absent.txt")


def test_decimal_precision_is_exact(tmp_path: Path) -> None:
    rows = [make_row(EcritureNum="OD1", Debit="0,10") for _ in range(3)]
    rows.append(make_row(EcritureNum="OD1", Credit="0,30"))
    report = validate(write_fec(tmp_path, rows))
    assert report.is_valid
    assert report.totals.debit == Decimal("0.30")
