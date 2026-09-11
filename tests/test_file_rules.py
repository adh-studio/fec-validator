from collections.abc import Sequence
from pathlib import Path

from fec_validator.columns import DEBIT_CREDIT_COLUMNS
from fec_validator.context import FileContext
from fec_validator.filename import parse_filename
from fec_validator.header import analyse_header
from fec_validator.models import Issue
from fec_validator.rules import FileRule
from fec_validator.rules.file_rules import (
    ClosingDateRule,
    ColumnCaseRule,
    ColumnOrderRule,
    FileNameRule,
    MissingColumnsRule,
    SeparatorRule,
    SirenRule,
    UnexpectedColumnsRule,
)


def make_ctx(
    name: str = "123456782FEC20251231.txt",
    header: Sequence[str] = DEBIT_CREDIT_COLUMNS,
    separator: str | None = "\t",
) -> FileContext:
    return FileContext(
        path=Path(name),
        filename=parse_filename(name),
        encoding="utf-8",
        separator=separator,
        header=analyse_header(header),
    )


def codes(rule: FileRule, ctx: FileContext) -> list[str]:
    issues: list[Issue] = list(rule.check(ctx))
    return [issue.code for issue in issues]


ALL_RULES: list[FileRule] = [
    FileNameRule(),
    SirenRule(),
    ClosingDateRule(),
    SeparatorRule(),
    MissingColumnsRule(),
    UnexpectedColumnsRule(),
    ColumnOrderRule(),
    ColumnCaseRule(),
]


def test_conforming_file_has_no_issue() -> None:
    ctx = make_ctx()
    assert [code for rule in ALL_RULES for code in codes(rule, ctx)] == []


def test_file_name() -> None:
    assert codes(FileNameRule(), make_ctx("export_compta.txt")) == ["FEC-F001"]


def test_siren() -> None:
    assert codes(SirenRule(), make_ctx("123456789FEC20251231.txt")) == ["FEC-F002"]
    assert codes(SirenRule(), make_ctx("export.txt")) == []


def test_closing_date() -> None:
    assert codes(ClosingDateRule(), make_ctx("123456782FEC20250231.txt")) == ["FEC-F003"]


def test_separator_is_fatal() -> None:
    ctx = make_ctx(header=[";".join(DEBIT_CREDIT_COLUMNS)], separator=None)
    assert codes(SeparatorRule(), ctx) == ["FEC-F004"]
    assert SeparatorRule.fatal
    # Header rules stay silent when the separator is unknown.
    assert codes(MissingColumnsRule(), ctx) == []
    assert codes(UnexpectedColumnsRule(), ctx) == []
    assert codes(ColumnCaseRule(), ctx) == []


def test_missing_columns_is_fatal() -> None:
    ctx = make_ctx(header=DEBIT_CREDIT_COLUMNS[:16])
    assert codes(MissingColumnsRule(), ctx) == ["FEC-F005"]
    assert MissingColumnsRule.fatal
    assert codes(ColumnOrderRule(), ctx) == []


def test_unexpected_columns() -> None:
    ctx = make_ctx(header=[*DEBIT_CREDIT_COLUMNS, "Commentaire"])
    issues = list(UnexpectedColumnsRule().check(ctx))
    assert [issue.code for issue in issues] == ["FEC-F006"]
    assert "'Commentaire'" in issues[0].message


def test_column_order() -> None:
    names = list(DEBIT_CREDIT_COLUMNS)
    names[0], names[1] = names[1], names[0]
    assert codes(ColumnOrderRule(), make_ctx(header=names)) == ["FEC-F007"]


def test_column_case() -> None:
    names = [name.upper() for name in DEBIT_CREDIT_COLUMNS]
    assert codes(ColumnCaseRule(), make_ctx(header=names)) == ["FEC-F008"] * 18
