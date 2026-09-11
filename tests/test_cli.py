"""End to end tests of the ``fec-check`` command."""

import io
import json
import runpy
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fec_factory import make_row, valid_rows, write_fec
from fec_validator import cli
from fec_validator.cli import app

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
ENV = {"COLUMNS": "200", "NO_COLOR": "1"}

runner = CliRunner()


def invoke(*args: str) -> tuple[int, str, str]:
    result = runner.invoke(app, list(args), env=ENV)
    return result.exit_code, result.stdout, result.stderr


def test_validate_valid_file(tmp_path: Path) -> None:
    code, out, _ = invoke("validate", str(write_fec(tmp_path, valid_rows())))
    assert code == 0
    assert "FICHIER CONFORME" in out
    assert "123456782 (clé de contrôle valide)" in out
    assert "du 01/01/2025 au 31/12/2025" in out
    assert "2 612,00" in out


def test_validate_file_with_errors(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[0]["CompteLib"] = ""
    rows[1]["Credit"] = "1 000,00"
    code, out, _ = invoke("validate", str(write_fec(tmp_path, rows)))
    assert code == 1
    assert "FICHIER NON CONFORME" in out
    assert "FEC-L002" in out
    assert "Le champ obligatoire CompteLib est vide." in out
    assert "séparateurs de milliers" in out


def test_validate_json(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[0]["CompteLib"] = ""
    code, out, _ = invoke("validate", str(write_fec(tmp_path, rows)), "--format", "json")
    assert code == 1
    data = json.loads(out)
    assert data["valid"] is False
    assert data["summary"]["by_rule"] == {"FEC-L002": 1}
    assert data["issues"][0]["line"] == 2
    assert data["issues"][0]["severity"] == "error"


def test_validate_strict_fails_on_warnings(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[0]["DateLet"] = ""
    path = str(write_fec(tmp_path, rows))
    assert invoke("validate", path)[0] == 0
    assert invoke("validate", path, "--strict")[0] == 1


def test_validate_period_options(tmp_path: Path) -> None:
    rows = valid_rows()
    for row in rows[:3]:
        row["EcritureDate"] = "20241215"
    path = str(write_fec(tmp_path, rows))
    code, out, _ = invoke("validate", path, "--debut", "20241201", "--fin", "2025-12-31")
    assert code == 0
    assert "du 01/12/2024 au 31/12/2025" in out
    assert "début supposé" not in out


@pytest.mark.parametrize(
    "args",
    [
        ("--debut", "20250231"),
        ("--fin", "31/12/2025"),
        ("--debut", "20251231", "--fin", "20250101"),
        ("--ignorer", "FEC-X000"),
        ("--max-anomalies", "0"),
    ],
)
def test_validate_bad_options(tmp_path: Path, args: tuple[str, ...]) -> None:
    code, _, err = invoke("validate", str(write_fec(tmp_path, valid_rows())), *args)
    assert code == 2
    assert err


def test_validate_ignore_rule(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[0]["CompteLib"] = ""
    path = str(write_fec(tmp_path, rows))
    assert invoke("validate", path, "--ignorer", "FEC-L002")[0] == 0


def test_validate_truncated_details(tmp_path: Path) -> None:
    rows = [make_row(EcritureNum=f"VT{i}", CompteLib="") for i in range(5)]
    code, out, _ = invoke("validate", str(write_fec(tmp_path, rows)), "--max-anomalies", "2")
    assert code == 1
    assert "Seules les 2 premières anomalies" in out


def test_validate_fatal_header(tmp_path: Path) -> None:
    code, out, _ = invoke("validate", str(write_fec(tmp_path, valid_rows(), separator=";")))
    assert code == 1
    assert "Analyse interrompue" in out
    assert "non reconnu" in out


def test_validate_non_conforming_name(tmp_path: Path) -> None:
    code, out, _ = invoke("validate", str(write_fec(tmp_path, valid_rows(), name="export.txt")))
    assert code == 0
    assert "non déterminé (nom de fichier non conforme)" in out
    assert "inconnu (préciser --debut et --fin)" in out


@pytest.mark.parametrize("command", ["validate", "balance"])
def test_unreadable_file_exit_code(tmp_path: Path, command: str) -> None:
    code, _, err = invoke(command, str(tmp_path / "absent.txt"))
    assert code == 2
    assert "Fichier introuvable" in err


def test_balance_display(tmp_path: Path) -> None:
    code, out, _ = invoke("balance", str(write_fec(tmp_path, valid_rows())))
    assert code == 0
    assert "Balance générale" in out
    assert "Fournisseurs" in out
    assert "-212,00" in out
    assert "8 comptes, 10 lignes lues" in out


def test_balance_csv(tmp_path: Path) -> None:
    rows = valid_rows()
    rows[0]["Debit"] = "1200.00"
    output = tmp_path / "balance.csv"
    code, out, _ = invoke("balance", str(write_fec(tmp_path, rows)), "-o", str(output))
    assert code == 0
    assert "Balance générale écrite dans" in out
    assert "1 ligne(s) ignorée(s)" in out
    content = output.read_text(encoding="utf-8-sig")
    assert content.startswith("CompteNum;CompteLib;TotalDebit;TotalCredit;Solde\n")


def test_balance_write_error(tmp_path: Path) -> None:
    code, _, err = invoke("balance", str(write_fec(tmp_path, valid_rows())), "-o", str(tmp_path))
    assert code == 2
    assert "impossible d'écrire" in err


def test_rules_command() -> None:
    code, out, _ = invoke("rules")
    assert code == 0
    assert "FEC-F001" in out
    assert "FEC-G002" in out


def test_version() -> None:
    code, out, _ = invoke("--version")
    assert code == 0
    assert out.startswith("fec-check ")


def test_examples_are_up_to_date() -> None:
    assert invoke("validate", str(EXAMPLES / "123456782FEC20251231.txt"))[0] == 0
    code, out, _ = invoke("validate", str(EXAMPLES / "987654321FEC20251231.txt"))
    assert code == 1
    assert "FEC-E001" in out


def test_main_and_module_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["fec-check", "--version"])
    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    assert exc_info.value.code == 0
    with pytest.raises(SystemExit):
        runpy.run_module("fec_validator", run_name="__main__")


def test_make_output_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    cli._make_output_safe()
    stream.write("\u2500 ok")
    stream.flush()
    assert stream.errors == "replace"
