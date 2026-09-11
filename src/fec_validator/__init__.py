"""Validation of French FEC files (Fichier des Écritures Comptables).

The public API is intentionally small:

* :func:`validate` streams a file through every registered rule and returns a
  :class:`ValidationReport`;
* :func:`compute_balance` builds the trial balance (balance générale);
* :mod:`fec_validator.rules` exposes the rule registry for custom rules.
"""

from importlib.metadata import PackageNotFoundError, version

from fec_validator.balance import AccountBalance, BalanceResult, compute_balance
from fec_validator.errors import FecReadError
from fec_validator.models import FiscalPeriod, Issue, Scope, Severity
from fec_validator.report import ValidationReport
from fec_validator.validator import validate

try:
    __version__ = version("fec-validator")
except PackageNotFoundError:  # pragma: no cover - only when running from a raw checkout
    __version__ = "0.0.0"

__all__ = [
    "AccountBalance",
    "BalanceResult",
    "FecReadError",
    "FiscalPeriod",
    "Issue",
    "Scope",
    "Severity",
    "ValidationReport",
    "__version__",
    "compute_balance",
    "validate",
]
