"""Balance générale (trial balance): totals per account, streamed."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import TextIO

from fec_validator.errors import FecReadError
from fec_validator.header import analyse_header
from fec_validator.parsing import ZERO, debit_credit, format_amount_fr
from fec_validator.reader import FecReader

CSV_HEADER = ("CompteNum", "CompteLib", "TotalDebit", "TotalCredit", "Solde")


@dataclass(slots=True)
class AccountBalance:
    """Totals of one general ledger account (CompteNum)."""

    compte_num: str
    compte_lib: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO

    @property
    def solde(self) -> Decimal:
        """Balance: positive when the account is in debit, negative in credit."""
        return self.debit - self.credit


@dataclass(slots=True)
class BalanceResult:
    """The trial balance and a few counters."""

    accounts: list[AccountBalance] = field(default_factory=list)
    line_count: int = 0
    skipped_lines: int = 0

    @property
    def total_debit(self) -> Decimal:
        """Sum of the debits of every account."""
        return sum((account.debit for account in self.accounts), ZERO)

    @property
    def total_credit(self) -> Decimal:
        """Sum of the credits of every account."""
        return sum((account.credit for account in self.accounts), ZERO)


def compute_balance(path: str | Path) -> BalanceResult:
    """Compute the balance générale of a FEC file.

    Lines whose amounts cannot be read, or that do not have the right number
    of fields, are skipped and counted in ``skipped_lines``. Run
    :func:`fec_validator.validate` to know why.

    :raises FecReadError: when the file cannot be read or its header is unusable.
    """
    path = Path(path)
    accounts: dict[str, AccountBalance] = {}
    result = BalanceResult()
    with FecReader(path) as reader:
        header = analyse_header(reader.header)
        if reader.separator is None or not header.usable:
            raise FecReadError(
                "En-tête inexploitable : séparateur non reconnu ou colonnes absentes. "
                "Lancer 'fec-check validate' pour le détail."
            )
        columns = header.columns
        expected = len(columns)
        for _number, values in reader.rows():
            result.line_count += 1
            if len(values) != expected:
                result.skipped_lines += 1
                continue
            fields = dict(zip(columns, values, strict=True))
            amounts = debit_credit(fields, header.layout)
            if amounts is None:
                result.skipped_lines += 1
                continue
            number = fields["CompteNum"]
            account = accounts.get(number)
            if account is None:
                account = accounts[number] = AccountBalance(number, fields["CompteLib"])
            elif not account.compte_lib:
                account.compte_lib = fields["CompteLib"]
            account.debit += amounts[0]
            account.credit += amounts[1]
    result.accounts = [accounts[number] for number in sorted(accounts)]
    return result


def write_balance_csv(result: BalanceResult, output: TextIO, *, delimiter: str = ";") -> None:
    """Write the balance as CSV with French number formatting (``1234,56``).

    The ``;`` delimiter lets a French Excel open the file directly.
    """
    writer = csv.writer(output, delimiter=delimiter, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for account in result.accounts:
        writer.writerow(
            (
                account.compte_num,
                account.compte_lib,
                format_amount_fr(account.debit),
                format_amount_fr(account.credit),
                format_amount_fr(account.solde),
            )
        )
