from datetime import date

import pytest

from fec_factory import context, make_line, make_sens_line
from fec_validator.columns import Layout
from fec_validator.models import FecLine, FiscalPeriod, Issue, Severity
from fec_validator.rules import LineRule
from fec_validator.rules.line_rules import (
    AmountFormatRule,
    AuxiliaryLabelRule,
    CurrencyCodeRule,
    CurrencyConsistencyRule,
    DateFormatRule,
    DebitAndCreditRule,
    FieldCountRule,
    FiscalYearRule,
    InferredStartRule,
    LettrageDateRule,
    MandatoryFieldsRule,
    NegativeAmountRule,
    SensRule,
    ValidDateRule,
)

SENS = context(layout=Layout.MONTANT_SENS)
INFERRED = context(FiscalPeriod(date(2025, 1, 1), date(2025, 12, 31), start_inferred=True))


def run(rule: LineRule, line: FecLine, ctx: object = None) -> list[Issue]:
    return list(rule.check(line, ctx if ctx is not None else context()))  # type: ignore[arg-type]


def test_valid_line_passes_every_rule() -> None:
    rules: list[LineRule] = [
        FieldCountRule(),
        MandatoryFieldsRule(),
        DateFormatRule(),
        AmountFormatRule(),
        DebitAndCreditRule(),
        SensRule(),
        NegativeAmountRule(),
        LettrageDateRule(),
        AuxiliaryLabelRule(),
        CurrencyConsistencyRule(),
        CurrencyCodeRule(),
        FiscalYearRule(),
        InferredStartRule(),
        ValidDateRule(),
    ]
    line = make_line(Debit="10,00")
    assert [issue for rule in rules for issue in run(rule, line)] == []


def test_field_count() -> None:
    line = make_line()
    assert run(FieldCountRule(), line) == []
    line.raw_count = 17
    issues = run(FieldCountRule(), line)
    assert [issue.code for issue in issues] == ["FEC-L001"]
    assert "17 champs" in issues[0].message
    assert FieldCountRule.structural


def test_mandatory_fields_one_issue_per_field() -> None:
    issues = run(MandatoryFieldsRule(), make_line(CompteLib="", PieceRef=""))
    assert [issue.column for issue in issues] == ["CompteLib", "PieceRef"]
    assert all(issue.severity is Severity.ERROR for issue in issues)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("EcritureDate", "20250230"),
        ("PieceDate", "2025-01-15"),
        ("ValidDate", "15/01/2025"),
        ("DateLet", "2025011"),
    ],
)
def test_date_format(column: str, value: str) -> None:
    issues = run(DateFormatRule(), make_line(**{column: value}))
    assert [(issue.code, issue.column) for issue in issues] == [("FEC-L003", column)]


def test_date_format_ignores_empty_values() -> None:
    assert run(DateFormatRule(), make_line(DateLet="", EcritureDate="")) == []


@pytest.mark.parametrize(
    ("column", "value", "hint"),
    [
        ("Debit", "1234.56", "virgule"),
        ("Credit", "1 234,56", "milliers"),
        ("Montantdevise", "12,5 USD", "format attendu"),
    ],
)
def test_amount_format(column: str, value: str, hint: str) -> None:
    issues = run(AmountFormatRule(), make_line(**{column: value}))
    assert len(issues) == 1
    assert issues[0].column == column
    assert hint in issues[0].message


def test_amount_format_montant_sens_layout() -> None:
    issues = run(AmountFormatRule(), make_sens_line(Montant="12.00"), SENS)
    assert [issue.column for issue in issues] == ["Montant"]


def test_debit_and_credit_on_same_line() -> None:
    assert run(DebitAndCreditRule(), make_line(Debit="10,00", Credit="0,00")) == []
    issues = run(DebitAndCreditRule(), make_line(Debit="10,00", Credit="5,00"))
    assert [issue.code for issue in issues] == ["FEC-L005"]
    # Not applicable to the Montant/Sens layout, nor to unreadable amounts.
    assert run(DebitAndCreditRule(), make_sens_line(), SENS) == []
    assert run(DebitAndCreditRule(), make_line(Debit="10.00", Credit="5,00")) == []


@pytest.mark.parametrize("sens", ["D", "C", "+1", "-1", "d"])
def test_sens_valid(sens: str) -> None:
    assert run(SensRule(), make_sens_line(Sens=sens), SENS) == []


def test_sens_invalid() -> None:
    issues = run(SensRule(), make_sens_line(Sens="X"), SENS)
    assert [issue.code for issue in issues] == ["FEC-L006"]
    assert run(SensRule(), make_line(), context()) == []


def test_negative_amount() -> None:
    issues = run(NegativeAmountRule(), make_line(Debit="-10,00"))
    assert [(issue.code, issue.severity) for issue in issues] == [("FEC-L007", Severity.WARNING)]
    assert run(NegativeAmountRule(), make_sens_line(Montant="-3,00"), SENS)[0].column == "Montant"
    assert run(NegativeAmountRule(), make_line(Debit="abc")) == []


def test_lettrage_without_date() -> None:
    issues = run(LettrageDateRule(), make_line(EcritureLet="AB"))
    assert [(issue.code, issue.severity) for issue in issues] == [("FEC-L008", Severity.WARNING)]
    assert run(LettrageDateRule(), make_line(EcritureLet="AB", DateLet="20250201")) == []


def test_auxiliary_label() -> None:
    issues = run(AuxiliaryLabelRule(), make_line(CompAuxNum="CLI001"))
    assert [issue.code for issue in issues] == ["FEC-L009"]
    assert run(AuxiliaryLabelRule(), make_line(CompAuxNum="CLI001", CompAuxLib="Client")) == []


@pytest.mark.parametrize(
    ("amount", "currency", "expected_column"),
    [
        ("100,00", "", "Idevise"),
        ("", "USD", "Montantdevise"),
        ("0,00", "USD", "Montantdevise"),
    ],
)
def test_currency_consistency(amount: str, currency: str, expected_column: str) -> None:
    issues = run(CurrencyConsistencyRule(), make_line(Montantdevise=amount, Idevise=currency))
    assert [(issue.code, issue.column) for issue in issues] == [("FEC-L010", expected_column)]


@pytest.mark.parametrize(
    ("amount", "currency"), [("", ""), ("0,00", ""), ("100,00", "USD"), ("-5,00", "GBP")]
)
def test_currency_consistency_ok(amount: str, currency: str) -> None:
    assert run(CurrencyConsistencyRule(), make_line(Montantdevise=amount, Idevise=currency)) == []


@pytest.mark.parametrize(("currency", "count"), [("USD", 0), ("usd", 1), ("US", 1), ("", 0)])
def test_currency_code(currency: str, count: int) -> None:
    assert len(run(CurrencyCodeRule(), make_line(Idevise=currency))) == count


def test_fiscal_year_after_closing() -> None:
    issues = run(FiscalYearRule(), make_line(EcritureDate="20260105"))
    assert [issue.code for issue in issues] == ["FEC-L012"]
    assert "postérieure" in issues[0].message


def test_fiscal_year_before_explicit_start() -> None:
    issues = run(FiscalYearRule(), make_line(EcritureDate="20241231"))
    assert "antérieure" in issues[0].message


def test_fiscal_year_before_inferred_start_is_only_a_warning() -> None:
    line = make_line(EcritureDate="20241231")
    assert run(FiscalYearRule(), line, INFERRED) == []
    issues = run(InferredStartRule(), line, INFERRED)
    assert [(issue.code, issue.severity) for issue in issues] == [("FEC-L013", Severity.WARNING)]
    assert run(InferredStartRule(), line, context()) == []


def test_fiscal_year_rules_skip_invalid_date_and_unknown_period() -> None:
    assert run(FiscalYearRule(), make_line(EcritureDate="2025")) == []
    assert run(InferredStartRule(), make_line(EcritureDate="2025"), INFERRED) == []
    assert run(FiscalYearRule(), make_line(EcritureDate="20300101"), context(FiscalPeriod())) == []


def test_valid_date_before_entry_date() -> None:
    issues = run(ValidDateRule(), make_line(EcritureDate="20250115", ValidDate="20250110"))
    assert [(issue.code, issue.severity) for issue in issues] == [("FEC-L014", Severity.WARNING)]
    assert run(ValidDateRule(), make_line(EcritureDate="20250115", ValidDate="20250115")) == []
    assert run(ValidDateRule(), make_line(ValidDate="bad")) == []
