"""Generate a large synthetic FEC and measure validation time and peak memory.

Usage::

    uv run python scripts/benchmark.py --lines 1000000 --dir bench

The file is generated once and reused on later runs. All data is fake.
"""

from __future__ import annotations

import argparse
import platform
import random
import sys
import time
from pathlib import Path

from fec_validator import compute_balance, validate
from fec_validator.columns import DEBIT_CREDIT_COLUMNS

ACCOUNTS = [
    ("41100000", "Clients"),
    ("40100000", "Fournisseurs"),
    ("60610000", "Fournitures non stockables"),
    ("60400000", "Achats de prestations"),
    ("62260000", "Honoraires"),
    ("70600000", "Prestations de services"),
    ("44571000", "TVA collectée"),
    ("44566000", "TVA déductible"),
    ("51200000", "Banque"),
]
JOURNALS = [("VT", "Ventes"), ("AC", "Achats"), ("BQ", "Banque"), ("OD", "Opérations diverses")]


def _amount(cents: int) -> str:
    return f"{cents // 100},{cents % 100:02d}"


def generate(path: Path, lines: int, seed: int = 42) -> None:
    """Write a balanced FEC of about ``lines`` data lines (entries of 2 to 4 lines)."""
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    entry = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("\t".join(DEBIT_CREDIT_COLUMNS) + "\r\n")
        while written < lines:
            entry += 1
            code, label = JOURNALS[entry % len(JOURNALS)]
            day = f"2025{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}"
            size = rng.randint(2, 4)
            debits = [rng.randint(100, 500_000) for _ in range(size - 1)]
            rows = [
                (account, cents, 0)
                for account, cents in zip(rng.sample(ACCOUNTS, size - 1), debits, strict=True)
            ]
            rows.append((ACCOUNTS[entry % len(ACCOUNTS)], 0, sum(debits)))
            for (number, account_label), debit, credit in rows:
                handle.write(
                    "\t".join(
                        (
                            code,
                            label,
                            f"{code}{entry:08d}",
                            day,
                            number,
                            account_label,
                            "",
                            "",
                            f"P{entry}",
                            day,
                            f"Écriture {entry}",
                            _amount(debit),
                            _amount(credit),
                            "",
                            "",
                            day,
                            "",
                            "",
                        )
                    )
                    + "\r\n"
                )
            written += size


def peak_memory_mib() -> float:
    """Peak resident memory of the current process, in MiB."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        psapi = ctypes.WinDLL("psapi")
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        )
        return counters.PeakWorkingSetSize / 2**20
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 2**20 if sys.platform == "darwin" else peak / 2**10


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lines", type=int, default=1_000_000)
    parser.add_argument("--dir", type=Path, default=Path("bench"))
    parser.add_argument("--balance", action="store_true", help="measure the balance too")
    args = parser.parse_args()

    path = args.dir / f"123456782FEC20251231_{args.lines}.txt"
    if not path.exists():
        started = time.perf_counter()
        generate(path, args.lines)
        print(f"generated {path} in {time.perf_counter() - started:.1f} s")
    size = path.stat().st_size / 2**20
    print(f"python {platform.python_version()} on {platform.platform()}")
    print(f"file: {size:.0f} MiB")

    started = time.perf_counter()
    report = validate(path)
    elapsed = time.perf_counter() - started
    print(
        f"validate: {elapsed:.1f} s, {report.totals.line_count} lines, "
        f"{report.totals.entry_count} entries, {report.error_count} errors, "
        f"{report.totals.line_count / elapsed:,.0f} lines/s"
    )
    print(f"peak memory after validate: {peak_memory_mib():.0f} MiB")

    if args.balance:
        started = time.perf_counter()
        result = compute_balance(path)
        print(f"balance: {time.perf_counter() - started:.1f} s, {len(result.accounts)} accounts")
        print(f"peak memory after balance: {peak_memory_mib():.0f} MiB")


if __name__ == "__main__":
    main()
