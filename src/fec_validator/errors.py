"""Exceptions raised by the library."""


class FecReadError(Exception):
    """The file cannot be read or decoded at all (missing, empty, not a text file...).

    The message is written in French because it is shown to end users as is.
    """
