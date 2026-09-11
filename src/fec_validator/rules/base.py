"""Rule base classes and the rule registry.

Adding a rule means writing a small class, decorating it with
:func:`register` and implementing ``check``. Nothing else needs to change:
the validator discovers rules through the registry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import ClassVar, TypeVar

from fec_validator.aggregation import EntryAggregate, Totals
from fec_validator.context import FileContext, ValidationContext
from fec_validator.models import FecLine, Issue, Scope, Severity


class Rule(ABC):
    """Common attributes of every rule."""

    code: ClassVar[str]
    severity: ClassVar[Severity]
    scope: ClassVar[Scope]
    title: ClassVar[str]
    """Short French description, shown in reports and in ``fec-check rules``."""

    def issue(
        self,
        message: str,
        *,
        line: int | None = None,
        column: str | None = None,
        entry: str | None = None,
    ) -> Issue:
        """Build an issue carrying this rule's code and severity."""
        return Issue(self.code, self.severity, message, line=line, column=column, entry=entry)


class FileRule(Rule):
    """Checks the file name, the encoding or the header."""

    scope = Scope.FILE
    fatal: ClassVar[bool] = False
    """When a fatal rule fires, the data lines cannot be interpreted and are not read."""

    @abstractmethod
    def check(self, ctx: FileContext) -> Iterator[Issue]:
        """Yield the issues found for the file."""


class LineRule(Rule):
    """Checks one data line in isolation."""

    scope = Scope.LINE
    structural: ClassVar[bool] = False
    """When a structural rule fires on a line, the other line rules are skipped for it."""

    @abstractmethod
    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        """Yield the issues found on ``line``."""


class EntryRule(Rule):
    """Checks an accounting entry once the whole file has been read."""

    scope = Scope.ENTRY

    @abstractmethod
    def check(self, entry: EntryAggregate, ctx: ValidationContext) -> Iterator[Issue]:
        """Yield the issues found for ``entry``."""


class GlobalRule(Rule):
    """Checks file level totals once the whole file has been read."""

    scope = Scope.GLOBAL

    @abstractmethod
    def check(self, totals: Totals, ctx: ValidationContext) -> Iterator[Issue]:
        """Yield the issues found for the whole file."""


RuleT = TypeVar("RuleT", bound=type[Rule])

_REGISTRY: dict[str, type[Rule]] = {}


def register(rule_class: RuleT) -> RuleT:
    """Class decorator adding a rule to the registry."""
    code = rule_class.code
    if code in _REGISTRY and _REGISTRY[code] is not rule_class:
        raise ValueError(f"Rule code {code} is already registered")
    _REGISTRY[code] = rule_class
    return rule_class


def unregister(code: str) -> None:
    """Remove a rule from the registry (mostly useful in tests)."""
    _REGISTRY.pop(code, None)


def registered_rules() -> list[type[Rule]]:
    """All registered rule classes, sorted by code."""
    return [_REGISTRY[code] for code in sorted(_REGISTRY)]


def get_rule(code: str) -> type[Rule] | None:
    """Return the rule class registered under ``code``, if any."""
    return _REGISTRY.get(code)


@dataclass(frozen=True, slots=True)
class RuleSet:
    """Instantiated rules, split by scope, ready to be run by the validator."""

    file_rules: tuple[FileRule, ...]
    line_rules: tuple[LineRule, ...]
    entry_rules: tuple[EntryRule, ...]
    global_rules: tuple[GlobalRule, ...]

    @classmethod
    def from_registry(cls, exclude: Iterable[str] = ()) -> RuleSet:
        """Instantiate every registered rule except the ``exclude`` codes."""
        excluded = {code.upper() for code in exclude}
        unknown = excluded - set(_REGISTRY)
        if unknown:
            raise ValueError("Code(s) de règle inconnu(s) : " + ", ".join(sorted(unknown)))
        rules = [
            rule_class() for rule_class in registered_rules() if rule_class.code not in excluded
        ]
        return cls(
            file_rules=tuple(rule for rule in rules if isinstance(rule, FileRule)),
            line_rules=tuple(rule for rule in rules if isinstance(rule, LineRule)),
            entry_rules=tuple(rule for rule in rules if isinstance(rule, EntryRule)),
            global_rules=tuple(rule for rule in rules if isinstance(rule, GlobalRule)),
        )
