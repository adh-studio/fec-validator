from fec_validator.columns import DEBIT_CREDIT_COLUMNS, MONTANT_SENS_COLUMNS, Layout
from fec_validator.header import analyse_header, detect_layout


def test_standard_header() -> None:
    header = analyse_header(DEBIT_CREDIT_COLUMNS)
    assert header.layout is Layout.DEBIT_CREDIT
    assert header.usable
    assert header.order_ok
    assert header.columns == DEBIT_CREDIT_COLUMNS
    assert not header.missing
    assert not header.unexpected
    assert not header.case_mismatches


def test_montant_sens_header() -> None:
    header = analyse_header(MONTANT_SENS_COLUMNS)
    assert header.layout is Layout.MONTANT_SENS
    assert header.usable
    assert header.expected == MONTANT_SENS_COLUMNS


def test_detect_layout_is_case_insensitive() -> None:
    assert detect_layout(["MONTANT", "sens"]) is Layout.MONTANT_SENS
    assert detect_layout(["Montant", "Sens", "Debit"]) is Layout.DEBIT_CREDIT


def test_missing_columns() -> None:
    header = analyse_header(DEBIT_CREDIT_COLUMNS[:-2])
    assert header.missing == ("Montantdevise", "Idevise")
    assert not header.usable


def test_unexpected_and_duplicate_columns() -> None:
    names = [*DEBIT_CREDIT_COLUMNS, "Extra", "Debit"]
    header = analyse_header(names)
    assert header.unexpected == ("Extra", "Debit")
    assert header.usable
    assert len(header.columns) == len(names)
    assert len(set(header.columns)) == len(names)


def test_wrong_order() -> None:
    names = list(DEBIT_CREDIT_COLUMNS)
    names[11], names[12] = names[12], names[11]
    header = analyse_header(names)
    assert header.usable
    assert not header.order_ok


def test_case_mismatch() -> None:
    names = [*DEBIT_CREDIT_COLUMNS[:-2], "MontantDevise", "IDevise"]
    header = analyse_header(names)
    assert header.usable
    assert header.case_mismatches == (("MontantDevise", "Montantdevise"), ("IDevise", "Idevise"))
    assert header.columns[-1] == "Idevise"
