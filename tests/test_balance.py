import io
from decimal import Decimal
from pathlib import Path

import pytest

from fec_factory import render_fec, to_montant_sens, valid_rows, write_fec
from fec_validator import FecReadError, compute_balance
from fec_validator.balance import write_balance_csv
from fec_validator.columns import Layout


def test_balance_per_account(tmp_path: Path) -> None:
    result = compute_balance(write_fec(tmp_path, valid_rows()))
    by_account = {account.compte_num: account for account in result.accounts}
    assert [account.compte_num for account in result.accounts] == sorted(by_account)
    clients = by_account["41100000"]
    assert (clients.debit, clients.credit, clients.solde) == (
        Decimal("1200.00"),
        Decimal("1200.00"),
        Decimal(0),
    )
    suppliers = by_account["40100000"]
    assert suppliers.solde == Decimal("-212.00")
    assert result.total_debit == result.total_credit == Decimal("2612.00")
    assert result.line_count == 10
    assert result.skipped_lines == 0


def test_balance_montant_sens(tmp_path: Path) -> None:
    rows = [to_montant_sens(row) for row in valid_rows()]
    result = compute_balance(write_fec(tmp_path, rows, layout=Layout.MONTANT_SENS))
    assert result.total_debit == Decimal("2612.00")


def test_balance_skips_unreadable_lines(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[0]["Debit"] = "1200.00"
    text = render_fec(rows) + "short\tline\r\n"
    path = tmp_path / "fec.txt"
    path.write_text(text, encoding="utf-8", newline="")
    result = compute_balance(path)
    assert result.skipped_lines == 2
    assert result.line_count == 11


def test_balance_keeps_first_non_empty_label(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[0]["CompteLib"] = ""
    result = compute_balance(write_fec(tmp_path, rows))
    labels = {account.compte_num: account.compte_lib for account in result.accounts}
    assert labels["41100000"] == "Clients"


def test_balance_unusable_header(tmp_path: Path) -> None:
    with pytest.raises(FecReadError, match="En-tête inexploitable"):
        compute_balance(write_fec(tmp_path, valid_rows(), separator=";"))


def test_balance_csv_format(tmp_path: Path) -> None:
    result = compute_balance(write_fec(tmp_path, valid_rows()))
    buffer = io.StringIO()
    write_balance_csv(result, buffer)
    lines = buffer.getvalue().splitlines()
    assert lines[0] == "CompteNum;CompteLib;TotalDebit;TotalCredit;Solde"
    assert "40100000;Fournisseurs;0,00;212,00;-212,00" in lines
    assert len(lines) == 1 + len(result.accounts)
