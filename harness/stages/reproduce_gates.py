"""Gate mekanis stage REPRODUCE — bagian pure-function.

Kontrak: docs/kontrak-output.md §9. Runner docker (yang menyediakan output
run-di-sandbox-segar) hidup terpisah; fungsi di sini tidak menyentuh disk.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_STATUS_RE = re.compile(r"^REPRO_STATUS: (PASS|FAIL)\s*$", re.MULTILINE)

_SLOT_RES = {
    "symptom": re.compile(r"^SYMPTOM:\s*(.+)$", re.MULTILINE),
    "trigger": re.compile(r"^TRIGGER:\s*(.+)$", re.MULTILINE),
    "expected": re.compile(r"^EXPECTED:\s*(.+)$", re.MULTILINE),
    "actual": re.compile(r"^ACTUAL:\s*(.+)$", re.MULTILINE),
    "repro_command": re.compile(r"^REPRO COMMAND:\s*(.+)$", re.MULTILINE),
    "confirmed_at_base": re.compile(r"^CONFIRMED-AT-BASE:\s*(yes|no)\s*$", re.MULTILINE),
}
_SLOT_LABELS = {
    "symptom": "SYMPTOM",
    "trigger": "TRIGGER",
    "expected": "EXPECTED",
    "actual": "ACTUAL",
    "repro_command": "REPRO COMMAND",
    "confirmed_at_base": "CONFIRMED-AT-BASE",
}


def parse_repro_status(output: str) -> str | None:
    """Token REPRO_STATUS terakhir di output (PASS/FAIL), atau None."""
    matches = _STATUS_RE.findall(output)
    return matches[-1] if matches else None


def parse_repro_md(text: str) -> dict:
    """Parse 5-slot repro.md; ValueError menyebut SEMUA slot yang hilang."""
    slots = {}
    missing = []
    for key, rx in _SLOT_RES.items():
        m = rx.search(text)
        if m:
            slots[key] = m.group(1).strip()
        else:
            missing.append(_SLOT_LABELS[key])
    if missing:
        raise ValueError(f"slot tidak ditemukan di repro.md: {', '.join(missing)}")
    return slots


@dataclass
class GateResult:
    verdict: str  # pass | fail | syntax-fail
    failures: list[str] = field(default_factory=list)


def evaluate_gates(repro_md_text: str,
                   fresh_run1_output: str, fresh_run1_exit: int,
                   fresh_run2_output: str, fresh_run2_exit: int,
                   scaffolding_error_markers: tuple[str, ...] = (
                       "ModuleNotFoundError", "ImproperlyConfigured"),
                   ) -> GateResult:
    """Evaluasi 4 gate REPRODUCE atas hasil 2 run di sandbox segar."""
    failures: list[str] = []

    try:
        slots = parse_repro_md(repro_md_text)
    except ValueError as e:
        return GateResult(verdict="syntax-fail", failures=[f"format repro.md: {e}"])

    for marker in scaffolding_error_markers:
        if marker in fresh_run1_output or marker in fresh_run2_output:
            return GateResult(verdict="fail", failures=[
                f"self-contained: error scaffolding terdeteksi ({marker}) di run sandbox segar"])

    status1 = parse_repro_status(fresh_run1_output)
    status2 = parse_repro_status(fresh_run2_output)
    if status1 is None or status2 is None:
        return GateResult(verdict="syntax-fail",
                          failures=["token REPRO_STATUS tidak ditemukan di output run sandbox segar"])

    if status1 == "PASS":
        failures.append(
            "anti-vacuous: REPRO_STATUS PASS di base commit — script tidak memperlihatkan bug")

    if status1 != status2:
        failures.append(
            f"idempoten: dua run sandbox segar tidak identik (run1={status1}, run2={status2})")

    if slots["confirmed_at_base"] != "yes":
        failures.append("CONFIRMED-AT-BASE bukan 'yes' — repro belum dikonfirmasi model")

    return GateResult(verdict="fail" if failures else "pass", failures=failures)
