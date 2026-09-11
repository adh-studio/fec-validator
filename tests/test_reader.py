from pathlib import Path

import pytest

from fec_factory import make_row, render_fec
from fec_validator.errors import FecReadError
from fec_validator.reader import FecReader, detect_encoding, detect_separator


def _write(tmp_path: Path, data: bytes, name: str = "fec.txt") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"JournalCode\tJournalLib\n", "utf-8"),
        ("Écriture\n".encode(), "utf-8"),
        (b"\xef\xbb\xbfJournalCode\n", "utf-8-sig"),
        ("Écriture 10 €\n".encode("cp1252"), "cp1252"),
        ("Écriture 10 €\n".encode("iso-8859-15"), "iso-8859-15"),
        ("Écriture\n".encode("latin-1"), "iso-8859-15"),
    ],
)
def test_detect_encoding(tmp_path: Path, data: bytes, expected: str) -> None:
    assert detect_encoding(_write(tmp_path, data)) == expected


@pytest.mark.parametrize("data", ["JournalCode\n".encode("utf-16"), b"PK\x03\x00\x00binary"])
def test_detect_encoding_rejects_utf16_and_binary(tmp_path: Path, data: bytes) -> None:
    with pytest.raises(FecReadError, match="UTF-16 ou fichier binaire"):
        detect_encoding(_write(tmp_path, data))


@pytest.mark.parametrize(
    ("header", "expected"),
    [("a\tb\tc", "\t"), ("a|b|c", "|"), ("a;b;c", None), ("a|b\tc\td", "\t")],
)
def test_detect_separator(header: str, expected: str | None) -> None:
    assert detect_separator(header) == expected


def test_reader_streams_rows_with_line_numbers(tmp_path: Path) -> None:
    text = render_fec([make_row(), make_row(EcritureNum="VT0002")], newline="\n")
    path = _write(tmp_path, (text + "\n  \n").encode())
    with FecReader(path) as reader:
        assert reader.separator == "\t"
        assert reader.header[0] == "JournalCode"
        rows = list(reader.rows())
    assert [number for number, _ in rows] == [2, 3]
    assert rows[1][1][2] == "VT0002"


def test_reader_strips_values_and_handles_crlf(tmp_path: Path) -> None:
    path = _write(tmp_path, b"A|B\r\n x | y \r\n")
    with FecReader(path) as reader:
        assert reader.header == ("A", "B")
        assert list(reader.rows()) == [(2, ["x", "y"])]


def test_reader_without_separator_keeps_raw_header(tmp_path: Path) -> None:
    path = _write(tmp_path, b"JournalCode;JournalLib\n")
    with FecReader(path) as reader:
        assert reader.separator is None
        assert reader.header == ("JournalCode;JournalLib",)


def test_reader_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FecReadError, match="introuvable"), FecReader(tmp_path / "absent.txt"):
        pass


def test_reader_directory(tmp_path: Path) -> None:
    with pytest.raises(FecReadError, match="pas un fichier"), FecReader(tmp_path):
        pass


@pytest.mark.parametrize("data", [b"", b"\n\nJournalCode\n", b"\xef\xbb\xbf"])
def test_reader_empty(tmp_path: Path, data: bytes) -> None:
    with pytest.raises(FecReadError, match="vide"), FecReader(_write(tmp_path, data)):
        pass


def test_reader_rows_requires_context(tmp_path: Path) -> None:
    reader = FecReader(_write(tmp_path, b"A\tB\n"))
    with pytest.raises(RuntimeError):
        list(reader.rows())


def test_reader_invalid_utf8_after_bom(tmp_path: Path) -> None:
    # Enough valid lines for the bad bytes to be decoded while streaming, not with the header.
    path = _write(tmp_path, b"\xef\xbb\xbfA\tB\n" + b"x\ty\n" * 50_000 + b"\xff\xfe\tx\n")
    with pytest.raises(FecReadError, match="octets invalides"), FecReader(path) as reader:
        list(reader.rows())


def test_reader_invalid_utf8_in_header_after_bom(tmp_path: Path) -> None:
    path = _write(tmp_path, b"\xef\xbb\xbfA\xff\tB\n")
    with pytest.raises(FecReadError, match="UTF-8 valide"), FecReader(path):
        pass


def test_reader_os_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write(tmp_path, b"A\tB\n")

    def refuse(*args: object, **kwargs: object) -> None:
        raise PermissionError(13, "Permission refusée")

    monkeypatch.setattr(Path, "open", refuse)
    with pytest.raises(FecReadError, match="Impossible de lire"), FecReader(path):
        pass


def test_reader_close_is_idempotent(tmp_path: Path) -> None:
    reader = FecReader(_write(tmp_path, b"A\tB\n"))
    with reader:
        pass
    reader.close()
