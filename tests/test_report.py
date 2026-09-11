import json
from pathlib import Path

import pytest

from fec_factory import valid_rows, write_fec
from fec_validator import validate
from fec_validator.models import Issue, Severity
from fec_validator.renderers import render_json
from fec_validator.report import IssueCollector


def issue(code: str = "FEC-L002", severity: Severity = Severity.ERROR) -> Issue:
    return Issue(code, severity, "message", line=2)


def test_collector_caps_details_but_counts_everything() -> None:
    collector = IssueCollector(max_per_rule=2)
    collector.extend(issue() for _ in range(5))
    collector.add(issue("FEC-L008", Severity.WARNING))
    assert len(collector.issues) == 3
    assert collector.counts == {"FEC-L002": 5, "FEC-L008": 1}
    assert (collector.error_count, collector.warning_count) == (5, 1)


def test_collector_rejects_negative_cap() -> None:
    with pytest.raises(ValueError, match="positive"):
        IssueCollector(max_per_rule=-1)


def test_issue_to_dict() -> None:
    assert issue().to_dict() == {
        "code": "FEC-L002",
        "severity": "error",
        "line": 2,
        "column": None,
        "entry": None,
        "message": "message",
    }


def test_exit_codes(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[0]["DateLet"] = ""  # FEC-L008, a warning
    report = validate(write_fec(tmp_path, rows))
    assert report.is_valid
    assert report.exit_code() == 0
    assert report.exit_code(strict=True) == 1


def test_json_serialization(tmp_path: Path) -> None:
    report = validate(write_fec(tmp_path, valid_rows()))
    data = json.loads(render_json(report))
    assert data["valid"] is True
    assert data["metadata"]["siren"] == "123456782"
    assert data["metadata"]["separator"] == "tab"
    assert data["metadata"]["layout"] == "debit_credit"
    assert data["metadata"]["period"] == {
        "start": "2025-01-01",
        "end": "2025-12-31",
        "start_inferred": True,
    }
    assert data["statistics"]["total_debit"] == "2612.00"
    assert data["statistics"]["entries"] == 4
    assert data["summary"] == {
        "errors": 0,
        "warnings": 0,
        "by_rule": {},
        "max_issues_per_rule": 100,
        "truncated": False,
    }


def test_summary_line(tmp_path: Path) -> None:
    report = validate(write_fec(tmp_path, valid_rows()))
    assert report.summary_line().startswith("123456782FEC20251231.txt : conforme (0 erreur(s)")
