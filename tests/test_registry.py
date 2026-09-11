import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from fec_factory import make_row, valid_rows, write_fec
from fec_validator import validate
from fec_validator.context import ValidationContext
from fec_validator.models import FecLine, Issue, Scope, Severity
from fec_validator.rules import (
    EntryRule,
    FileRule,
    GlobalRule,
    LineRule,
    RuleSet,
    get_rule,
    register,
    registered_rules,
    unregister,
)

CODE_RE = re.compile(r"FEC-[FLEG]\d{3}")
SCOPE_PREFIX = {Scope.FILE: "F", Scope.LINE: "L", Scope.ENTRY: "E", Scope.GLOBAL: "G"}


def test_every_rule_is_well_described() -> None:
    rules = registered_rules()
    assert len(rules) == 26
    for rule in rules:
        assert CODE_RE.fullmatch(rule.code), rule.code
        assert rule.code[4] == SCOPE_PREFIX[rule.scope], rule.code
        assert rule.title
        assert rule.severity in (Severity.ERROR, Severity.WARNING)
        assert "\u2014" not in rule.title
        assert "\u2013" not in rule.title


def test_ruleset_splits_rules_by_scope() -> None:
    ruleset = RuleSet.from_registry()
    assert all(isinstance(rule, FileRule) for rule in ruleset.file_rules)
    assert all(isinstance(rule, LineRule) for rule in ruleset.line_rules)
    assert all(isinstance(rule, EntryRule) for rule in ruleset.entry_rules)
    assert all(isinstance(rule, GlobalRule) for rule in ruleset.global_rules)
    total = sum(
        len(group)
        for group in (
            ruleset.file_rules,
            ruleset.line_rules,
            ruleset.entry_rules,
            ruleset.global_rules,
        )
    )
    assert total == len(registered_rules())


def test_ruleset_exclude_is_case_insensitive() -> None:
    ruleset = RuleSet.from_registry(exclude=["fec-l002"])
    assert "FEC-L002" not in {rule.code for rule in ruleset.line_rules}


def test_ruleset_unknown_code() -> None:
    with pytest.raises(ValueError, match="FEC-X999"):
        RuleSet.from_registry(exclude=["FEC-X999"])


def test_duplicate_code_is_refused() -> None:
    existing = get_rule("FEC-L002")
    assert existing is not None
    # Registering the same class twice is harmless.
    assert register(existing) is existing

    class Clash(LineRule):
        code = "FEC-L002"
        severity = Severity.ERROR
        title = "Doublon"

        def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
            yield from ()

    with pytest.raises(ValueError, match="already registered"):
        register(Clash)


def test_custom_rule_is_picked_up_by_the_validator(tmp_path: Path) -> None:
    @register
    class NoCashAccount(LineRule):
        code = "FEC-L901"
        severity = Severity.WARNING
        title = "Compte de caisse utilisé"

        def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
            if line.get("CompteNum").startswith("53"):
                yield self.issue("Compte de caisse.", line=line.number, column="CompteNum")

    try:
        rows = [*valid_rows(), make_row(EcritureNum="VT0009", CompteNum="53000000")]
        rows.append(make_row(EcritureNum="VT0009", CompteNum="53000000"))
        report = validate(write_fec(tmp_path, rows))
        assert report.counts == {"FEC-L901": 2}
        assert report.is_valid
    finally:
        unregister("FEC-L901")
    assert get_rule("FEC-L901") is None
