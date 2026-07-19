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
        raise ValueError(f"missing slots in localize.md: {', '.join(missing)}")

    m = _LINES_RE.match(slots["lines"])
    if not m:
        raise ValueError(
            f"slot lines must be N-M (numbers), got: {slots['lines']!r}")
    start, end = int(m.group(1)), int(m.group(2))
    if start > end:
        raise ValueError(f"slot lines reversed: {start}-{end}")
    slots["lines"] = (start, end)
    return slots


@dataclass
class LocalizeResult:
    verdict: str  # pass | fail | syntax-fail
    failures: list[str] = field(default_factory=list)

# Catatan boundary (framing Mirza 2026-07-19): product (harness + model)
# gold-blind total — evaluasi kebenaran vs gold patch hidup TERPISAH di
# lapisan test-system: eval/localize_gold_eval.py.


def evaluate_localize_gates(md_text: str, file_exists: bool,
                            file_line_count: int | None) -> LocalizeResult:
    try:
        slots = parse_localize_md(md_text)
    except ValueError as e:
        return LocalizeResult(verdict="syntax-fail",
                              failures=[f"localize.md format: {e}"])

    failures: list[str] = []
    start, end = slots["lines"]

    if not file_exists:
        failures.append(f"file does not exist in the repo: {slots['file']}")
    else:
        if end - start + 1 > MAX_SPAN:
            failures.append(
                f"lines range too wide ({end - start + 1} lines > "
                f"{MAX_SPAN}) — a map must point at a site, not a region")
        if file_line_count is not None and end > file_line_count:
            failures.append(
                f"lines {start}-{end} extend beyond the end of file "
                f"({file_line_count} lines)")

    return LocalizeResult(verdict="fail" if failures else "pass",
                          failures=failures)
