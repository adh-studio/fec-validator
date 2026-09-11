"""Low level reading: encoding and separator detection, line streaming.

Nothing here keeps more than one line in memory, so files of several
gigabytes can be processed.
"""

from __future__ import annotations

import codecs
import re
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType
from typing import IO

from fec_validator.errors import FecReadError

_CHUNK_SIZE = 1 << 20
_C1_CONTROLS = re.compile(rb"[\x80-\x9f]")

TAB = "\t"
PIPE = "|"

ENCODING_LABELS = {
    "utf-8-sig": "UTF-8 avec BOM",
    "utf-8": "UTF-8",
    "cp1252": "Windows-1252 (repli)",
    "iso-8859-15": "ISO-8859-15 (repli)",
}
SEPARATOR_LABELS = {TAB: "tabulation", PIPE: "barre verticale (|)"}
SEPARATOR_KEYS = {TAB: "tab", PIPE: "pipe"}


def detect_encoding(path: Path) -> str:
    """Detect the text encoding of a FEC file.

    UTF-8 (with or without BOM) is tried first on the whole file, chunk by
    chunk. Otherwise the file is assumed to be single byte: Windows-1252 when
    bytes in the 0x80-0x9F range are present (they are printable characters
    there, such as the euro sign), ISO-8859-15 otherwise.
    """
    with path.open("rb") as handle:
        head = handle.read(4)
        if head.startswith(codecs.BOM_UTF8):
            return "utf-8-sig"
        if head.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)) or b"\x00" in head:
            raise FecReadError(
                "Encodage non pris en charge (UTF-16 ou fichier binaire) : "
                "le FEC doit être un fichier texte UTF-8 ou ISO-8859-15."
            )
        handle.seek(0)
        decoder = codecs.getincrementaldecoder("utf-8")()
        try:
            while chunk := handle.read(_CHUNK_SIZE):
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            pass
        else:
            return "utf-8"
        handle.seek(0)
        while chunk := handle.read(_CHUNK_SIZE):
            if _C1_CONTROLS.search(chunk):
                return "cp1252"
        return "iso-8859-15"


def detect_separator(header: str) -> str | None:
    """Return the field separator used by the header line (tab or pipe), if any."""
    tabs = header.count(TAB)
    pipes = header.count(PIPE)
    if tabs == 0 and pipes == 0:
        return None
    return TAB if tabs >= pipes else PIPE


class FecReader:
    """Context manager streaming the data lines of a FEC file.

    Usage::

        with FecReader(path) as reader:
            print(reader.header)
            for number, values in reader.rows():
                ...

    ``number`` is the physical line number in the file (the header is line 1).
    Blank lines are skipped.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.encoding = ""
        self.separator: str | None = None
        self.header: tuple[str, ...] = ()
        self._handle: IO[str] | None = None

    def __enter__(self) -> FecReader:
        self._open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying file."""
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def _open(self) -> None:
        path = self.path
        if not path.exists():
            raise FecReadError(f"Fichier introuvable : {path}")
        if not path.is_file():
            raise FecReadError(f"Ce chemin n'est pas un fichier : {path}")
        try:
            self.encoding = detect_encoding(path)
            # cp1252 leaves five bytes undefined: they are replaced instead of
            # aborting the whole analysis.
            errors = "replace" if self.encoding == "cp1252" else "strict"
            self._handle = path.open(encoding=self.encoding, errors=errors, newline=None)
            header_line = self._handle.readline()
        except OSError as exc:
            raise FecReadError(f"Impossible de lire le fichier {path} : {exc.strerror}") from exc
        except UnicodeDecodeError as exc:
            self.close()
            raise FecReadError(f"Le fichier {path} n'est pas un texte UTF-8 valide.") from exc
        header_line = header_line.rstrip("\r\n")
        if not header_line.strip():
            self.close()
            raise FecReadError(f"Le fichier est vide ou sa première ligne est vide : {path}")
        self.separator = detect_separator(header_line)
        if self.separator is None:
            self.header = (header_line.strip(),)
        else:
            self.header = tuple(name.strip() for name in header_line.split(self.separator))

    def rows(self) -> Iterator[tuple[int, list[str]]]:
        """Yield ``(line_number, values)`` for every non blank data line."""
        if self._handle is None:
            raise RuntimeError("FecReader must be used as a context manager")
        separator = self.separator or TAB
        try:
            for number, raw in enumerate(self._handle, start=2):
                text = raw.rstrip("\r\n")
                if not text.strip():
                    continue
                yield number, [value.strip() for value in text.split(separator)]
        except UnicodeDecodeError as exc:
            raise FecReadError(
                f"Le fichier {self.path} contient des octets invalides pour l'encodage "
                f"{self.encoding}."
            ) from exc
