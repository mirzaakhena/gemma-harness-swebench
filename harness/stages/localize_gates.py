"""Gate mekanis stage LOCALIZE — bagian pure-function.

Kontrak: docs/kontrak-output.md §10 (SATU format localize.md) + lever P25:
rentang lines sempit (<= MAX_SPAN), file harus ada, rentang di dalam file.
Cek keberadaan/panjang file dilakukan runner (docker); di sini logika murni.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_SPAN = 200

_SLOT_RES = {
    "chosen": re.compile(r"^chosen:\s*(.+)$", re.MULTILINE),
    "file": re.compile(r"^file:\s*(.+)$", re.MULTILINE),
    "lines": re.compile(r"^lines:\s*(.+)$", re.MULTILINE),
    "what": re.compile(r"^what:\s*(.+)$", re.MULTILINE),
    "why": re.compile(r"^why:\s*(.+)$", re.MULTILINE),
    "evidence": re.compile(r"^evidence:\s*(.+)$", re.MULTILINE),
}
_LINES_RE = re.compile(r"^(\d+)\s*-\s*(\d+)$")


def parse_localize_md(text: str) -> dict:
    """Parse localize.md; ValueError menyebut SEMUA slot yang bermasalah."""
    slots: dict = {}
    missing = []
    for key, rx in _SLOT_RES.items():
        m = rx.search(text)
        if m:
            slots[key] = m.group(1).strip()
        else:
            missing.append(key)
    if missing:
        raise ValueError(f"slot tidak ditemukan di localize.md: {', '.join(missing)}")

    m = _LINES_RE.match(slots["lines"])
    if not m:
        raise ValueError(
            f"slot lines harus berformat N-M (angka), dapat: {slots['lines']!r}")
    start, end = int(m.group(1)), int(m.group(2))
    if start > end:
        raise ValueError(f"slot lines terbalik: {start}-{end}")
    slots["lines"] = (start, end)
    return slots


@dataclass
class LocalizeResult:
    verdict: str  # pass | fail | syntax-fail
    failures: list[str] = field(default_factory=list)


def evaluate_localize_gates(md_text: str, file_exists: bool,
                            file_line_count: int | None) -> LocalizeResult:
    try:
        slots = parse_localize_md(md_text)
    except ValueError as e:
        return LocalizeResult(verdict="syntax-fail",
                              failures=[f"format localize.md: {e}"])

    failures: list[str] = []
    start, end = slots["lines"]

    if not file_exists:
        failures.append(f"file tidak ada di repo: {slots['file']}")
    else:
        if end - start + 1 > MAX_SPAN:
            failures.append(
                f"rentang lines terlalu lebar ({end - start + 1} baris > "
                f"{MAX_SPAN}) — peta harus menunjuk situs, bukan wilayah")
        if file_line_count is not None and end > file_line_count:
            failures.append(
                f"lines {start}-{end} melewati akhir file "
                f"({file_line_count} baris)")

    return LocalizeResult(verdict="fail" if failures else "pass",
                          failures=failures)
