from decimal import Decimal

from fec_factory import context, make_line
from fec_validator.aggregation import Aggregator, EntryAggregate, Totals
from fec_validator.rules.entry_rules import BalancedEntryRule, SingleDateRule
from fec_validator.rules.global_rules import BalancedFileRule, EmptyFileRule


def entry(**overrides: object) -> EntryAggregate:
    values: dict[str, object] = {
        "journal_code": "VT",
        "number": "VT0001",
        "first_line": 2,
        "date": "20250115",
        "debit": Decimal("100.00"),
        "credit": Decimal("100.00"),
        "line_count": 2,
    }
    values.update(overrides)
    return EntryAggregate(**values)  # type: ignore[arg-type]


def test_balanced_entry() -> None:
    assert list(BalancedEntryRule().check(entry(), context())) == []


def test_unbalanced_entry() -> None:
    issues = list(BalancedEntryRule().check(entry(credit=Decimal("99.99")), context()))
    assert [issue.code for issue in issues] == ["FEC-E001"]
    assert issues[0].entry == "VT/VT0001"
    assert issues[0].line == 2
    assert "écart 0,01" in issues[0].message


def test_unbalanced_entry_with_invalid_amount_is_not_reported_twice() -> None:
    faulty = entry(credit=Decimal(0), has_invalid_amount=True)
    assert list(BalancedEntryRule().check(faulty, context())) == []


def test_single_date() -> None:
    assert list(SingleDateRule().check(entry(), context())) == []
    issues = list(
        SingleDateRule().check(entry(other_date="20250116", other_date_line=3), context())
    )
    assert [(issue.code, issue.line) for issue in issues] == [("FEC-E002", 3)]


def test_balanced_file() -> None:
    totals = Totals(line_count=2, debit=Decimal(5), credit=Decimal(5))
    assert list(BalancedFileRule().check(totals, context())) == []


def test_unbalanced_file_mentions_unreadable_lines() -> None:
    totals = Totals(line_count=3, debit=Decimal(5), credit=Decimal(4), invalid_amount_lines=1)
    issues = list(BalancedFileRule().check(totals, context()))
    assert [issue.code for issue in issues] == ["FEC-G001"]
    assert "écart 1,00" in issues[0].message
    assert "1 ligne(s) au montant illisible" in issues[0].message


def test_empty_file() -> None:
    assert [issue.code for issue in EmptyFileRule().check(Totals(), context())] == ["FEC-G002"]
    assert list(EmptyFileRule().check(Totals(line_count=1), context())) == []


def test_aggregator_tracks_entries_dates_and_invalid_amounts() -> None:
    aggregator = Aggregator()
    aggregator.add(make_line(2, Debit="10,00"), (Decimal(10), Decimal(0)))
    aggregator.add(make_line(3, EcritureDate="20250116"), (Decimal(0), Decimal(10)))
    aggregator.add(make_line(4, EcritureDate="20250117"), None)
    aggregator.add(make_line(5, EcritureNum="VT0002"), (Decimal(1), Decimal(1)))
    aggregator.add_malformed()
    totals = aggregator.finish()
    first = aggregator.entries[("VT", "VT0001")]
    assert (first.debit, first.credit, first.line_count) == (Decimal(10), Decimal(10), 3)
    assert (first.other_date, first.other_date_line) == ("20250116", 3)
    assert first.has_invalid_amount
    assert totals.entry_count == 2
    assert totals.line_count == 5
    assert totals.malformed_lines == 1
    assert totals.invalid_amount_lines == 1
    assert (totals.debit, totals.credit) == (Decimal(11), Decimal(11))
