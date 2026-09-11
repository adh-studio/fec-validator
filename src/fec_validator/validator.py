"""Orchestration: read the file once and run every rule on the stream."""

from __future__ import annotations

import time
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from fec_validator.aggregation import Aggregator
from fec_validator.context import FileContext, ValidationContext
from fec_validator.filename import parse_filename, resolve_period
from fec_validator.header import HeaderAnalysis, analyse_header
from fec_validator.models import FecLine, Issue
from fec_validator.parsing import debit_credit
from fec_validator.reader import FecReader
from fec_validator.report import DEFAULT_MAX_ISSUES_PER_RULE, IssueCollector, ValidationReport
from fec_validator.rules import RuleSet


def validate(
    path: str | Path,
    *,
    start: date | None = None,
    end: date | None = None,
    max_issues_per_rule: int = DEFAULT_MAX_ISSUES_PER_RULE,
    exclude: Iterable[str] = (),
    ruleset: RuleSet | None = None,
) -> ValidationReport:
    """Validate a FEC file and return the report.

    :param path: the FEC file.
    :param start: fiscal year start; inferred from the closing date if omitted.
    :param end: fiscal year end; taken from the file name if omitted.
    :param max_issues_per_rule: number of detailed issues kept per rule
        (all occurrences are still counted).
    :param exclude: rule codes to skip.
    :param ruleset: explicit rules to run, instead of the registry.
    :raises FecReadError: when the file cannot be read at all.
    """
    started = time.perf_counter()
    path = Path(path)
    rules = ruleset if ruleset is not None else RuleSet.from_registry(exclude)
    collector = IssueCollector(max_issues_per_rule)
    info = parse_filename(path.name)
    period = resolve_period(info, start, end)
    aggregator = Aggregator()

    with FecReader(path) as reader:
        header = analyse_header(reader.header)
        file_ctx = FileContext(
            path=path,
            filename=info,
            encoding=reader.encoding,
            separator=reader.separator,
            header=header,
        )
        fatal = reader.separator is None or not header.usable
        for file_rule in rules.file_rules:
            for issue in file_rule.check(file_ctx):
                collector.add(issue)
                fatal = fatal or file_rule.fatal
        ctx = ValidationContext(
            period=period, layout=header.layout, column_count=len(header.columns)
        )
        if not fatal:
            _scan_lines(reader, header, rules, ctx, collector, aggregator)

    totals = aggregator.finish()
    if not fatal:
        for entry in aggregator.entries.values():
            for entry_rule in rules.entry_rules:
                collector.extend(entry_rule.check(entry, ctx))
        for global_rule in rules.global_rules:
            collector.extend(global_rule.check(totals, ctx))

    return ValidationReport(
        path=path,
        encoding=reader.encoding,
        separator=reader.separator,
        layout=None if fatal else header.layout,
        filename=info,
        period=period,
        totals=totals,
        issues=sorted(collector.issues, key=_issue_order),
        counts=dict(collector.counts),
        error_count=collector.error_count,
        warning_count=collector.warning_count,
        fatal=fatal,
        max_issues_per_rule=max_issues_per_rule,
        duration_seconds=time.perf_counter() - started,
    )


def _issue_order(issue: Issue) -> tuple[int, int]:
    """Sort key: file issues first, then by line number, whole file issues last.

    ``sorted`` is stable, so issues of the same line keep the rule order.
    """
    if issue.line is None:
        return (2, 0) if issue.code.startswith("FEC-G") else (0, 0)
    return (1, issue.line)


def _scan_lines(
    reader: FecReader,
    header: HeaderAnalysis,
    rules: RuleSet,
    ctx: ValidationContext,
    collector: IssueCollector,
    aggregator: Aggregator,
) -> None:
    """Stream the data lines through the line rules and the aggregator."""
    columns = header.columns
    layout = ctx.layout
    structural = [rule for rule in rules.line_rules if rule.structural]
    regular = [rule for rule in rules.line_rules if not rule.structural]
    add = collector.add
    for number, values in reader.rows():
        line = FecLine(number, dict(zip(columns, values, strict=False)), len(values))
        broken = False
        for rule in structural:
            for issue in rule.check(line, ctx):
                add(issue)
                broken = True
        if broken:
            aggregator.add_malformed()
            continue
        for rule in regular:
            for issue in rule.check(line, ctx):
                add(issue)
        aggregator.add(line, debit_credit(line.fields, layout))
