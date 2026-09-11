"""Validation rules.

Importing this package registers every built-in rule. Rule codes follow the
scope of the check:

* ``FEC-Fxxx``: file name, encoding, header;
* ``FEC-Lxxx``: one data line;
* ``FEC-Exxx``: one accounting entry (JournalCode + EcritureNum);
* ``FEC-Gxxx``: whole file.
"""

from fec_validator.rules import entry_rules, file_rules, global_rules, line_rules
from fec_validator.rules.base import (
    EntryRule,
    FileRule,
    GlobalRule,
    LineRule,
    Rule,
    RuleSet,
    get_rule,
    register,
    registered_rules,
    unregister,
)

__all__ = [
    "EntryRule",
    "FileRule",
    "GlobalRule",
    "LineRule",
    "Rule",
    "RuleSet",
    "entry_rules",
    "file_rules",
    "get_rule",
    "global_rules",
    "line_rules",
    "register",
    "registered_rules",
    "unregister",
]
