"""Gate mekanis stage FIX — bagian pure-function.

Spec: docs/superpowers/specs/2026-07-20-fix-stage-design.md §4/§7.
STANDAR TUNGGAL: fungsi-fungsi di sini adalah satu-satunya definisi
"patch sah + flip" — dipakai pre-check DONE driver DAN gate L1 lewat
fix_patch_runner.evaluate_patch_in_fresh_world (Prinsip Stabilisasi §4).
Eksekusi docker hidup di fix_patch_runner; di sini logika murni.
Token PASS = exact_status (baris-eksak, standar tunggal fase R).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from harness.stages.gemma_protocol import exact_status

_DIFF_NEW_RE = re.compile(r"^\+\+\+\s+(?:b/)?(.+?)\s*$", re.MULTILINE)
_DIFF_OLD_RE = re.compile(r"^---\s+(?:a/)?(.+?)\s*$", re.MULTILINE)


def diff_touched_files(diff_text: str) -> set[str]:
    """Himpunan path file yang disentuh unified diff (logika sama dengan
    eval.localize_gold_eval.gold_touched_files; duplikat sengaja — product
    realm tidak mengimpor realm dev eval/)."""
    files: set[str] = set()
    old_paths = _DIFF_OLD_RE.findall(diff_text)
    new_paths = _DIFF_NEW_RE.findall(diff_text)
    for path in new_paths:
        if path != "/dev/null":
            files.add(path)
    for path in old_paths:
        if path != "/dev/null" and path not in files:
            files.add(path)
    paired_new = set(new_paths)
    if "/dev/null" not in paired_new:
        files -= (set(old_paths) - paired_new)
    return files


@dataclass
class FixPatchResult:
    """Hasil terstruktur evaluasi patch — bahan feedback kaya + telemetri
    event retry (alasan, pair status/exit/tail) SEJAK HARI PERTAMA."""
    ok: bool
    reason: str | None  # None|empty-diff|off-candidate-files|apply-failed|pair-not-pass|timeout
    failures: list[str] = field(default_factory=list)
    touched: tuple[str, ...] = ()
    status1: str | None = None
    status2: str | None = None
    exit1: int | None = None
    exit2: int | None = None
    run1_tail: str = ""
    run2_tail: str = ""


def _tail(s: str, n: int = 800) -> str:
    return s if len(s) <= n else s[-n:]


def patch_static_result(diff_text: str,
                        candidate_file: str) -> FixPatchResult | None:
    """Cek statis (tanpa docker): diff non-empty + pagar edit mekanis —
    hanya file kandidat aktif. None = lolos, lanjut ke dunia segar."""
    if not diff_text.strip():
        return FixPatchResult(ok=False, reason="empty-diff", failures=[
            "diff is empty — no change recorded in the work container"])
    touched = {p.lstrip("/") for p in diff_touched_files(diff_text)}
    if not touched:
        return FixPatchResult(ok=False, reason="empty-diff", failures=[
            "diff has no file headers — no change recorded"])
    stray = sorted(touched - {candidate_file.lstrip("/")})
    if stray:
        return FixPatchResult(
            ok=False, reason="off-candidate-files",
            failures=["diff touches files outside the candidate: "
                      + ", ".join(stray)],
            touched=tuple(sorted(touched)))
    return None


def apply_failed_result(apply_output: str) -> FixPatchResult:
    return FixPatchResult(ok=False, reason="apply-failed", failures=[
        "patch does not apply cleanly: " + _tail(apply_output.strip(), 400)])


def evaluate_pair_outputs(diff_text: str, candidate_file: str,
                          run1_output: str, run1_exit: int,
                          run2_output: str, run2_exit: int) -> FixPatchResult:
    """Vonis pair 2x container segar ber-patch: keduanya wajib mencetak
    REPRO_STATUS: PASS baris-eksak (exact_status — standar tunggal)."""
    touched = tuple(sorted(diff_touched_files(diff_text)))
    s1, s2 = exact_status(run1_output), exact_status(run2_output)
    base = dict(touched=touched, status1=s1, status2=s2,
                exit1=run1_exit, exit2=run2_exit,
                run1_tail=_tail(run1_output.strip()),
                run2_tail=_tail(run2_output.strip()))
    if ("[runner] TIMEOUT" in run1_output
            or "[runner] TIMEOUT" in run2_output):
        return FixPatchResult(ok=False, reason="timeout", failures=[
            "frozen repro timed out in the patched fresh container"], **base)
    if s1 == "PASS" and s2 == "PASS":
        return FixPatchResult(ok=True, reason=None, **base)
    return FixPatchResult(ok=False, reason="pair-not-pass", failures=[
        f"patched fresh pair not PASS,PASS (run1={s1}, run2={s2})"], **base)


def fix_rejection_message(r: FixPatchResult, candidate_file: str) -> str:
    """Feedback English penolakan DONE — alasan konkret per kelas kegagalan
    (Prinsip Stabilisasi §5: feedback kaya, bukan label generik)."""
    if r.reason == "empty-diff":
        return (f"Not done yet: the repository shows no change yet — your "
                f"fix belongs in {candidate_file}. Edit that file, run "
                "`python /testbed/.pipe/repro.py` to see REPRO_STATUS: "
                "PASS, then declare DONE again.")
    if r.reason == "off-candidate-files":
        stray = ", ".join(f for f in r.touched
                          if f != candidate_file.lstrip("/"))
        return (f"Not done yet: your change touches {stray} — your edit "
                f"site is {candidate_file}. Restore the other files "
                "(`git checkout -- <path>`) so the whole fix lives in "
                f"{candidate_file}, then declare DONE again.")
    if r.reason == "apply-failed":
        return ("Not done yet: your change could not be applied to a clean "
                "copy of the repository:\n" + r.failures[0] + "\n"
                "Keep your edits ordinary in-place file modifications, "
                "then declare DONE again.")
    if r.reason == "timeout":
        return ("Not done yet: with your change applied to a clean copy of "
                "the repository, the frozen repro did not finish in time — "
                "your change makes the scenario hang. Rework it so "
                "`python /testbed/.pipe/repro.py` terminates and prints "
                "REPRO_STATUS: PASS, then declare DONE again.")
    return ("Not done yet: I applied your change to a clean copy of the "
            "repository and ran the frozen repro twice; the runs did not "
            f"both print REPRO_STATUS: PASS (run1={r.status1}, "
            f"run2={r.status2}).\n"
            f"Run 1 output tail:\n{r.run1_tail}\n"
            f"Run 2 output tail:\n{r.run2_tail}\n"
            "Rework your fix, run the repro to see REPRO_STATUS: PASS, "
            "then declare DONE again.")


# --- fix.md: slot interpretif model + slot mekanis harness ------------------

_FIX_SLOT_RES = {
    "what_changed": re.compile(r"^WHAT CHANGED:\s*(.+)$", re.MULTILINE),
    "why": re.compile(r"^WHY:\s*(.+)$", re.MULTILINE),
    "file": re.compile(r"^FILE:\s*(.+)$", re.MULTILINE),
    "candidate": re.compile(r"^CANDIDATE:\s*(\d+)\s*$", re.MULTILINE),
    "repro": re.compile(r"^REPRO:\s*(.+)$", re.MULTILINE),
}
_FIX_SLOT_LABELS = {
    "what_changed": "WHAT CHANGED", "why": "WHY", "file": "FILE",
    "candidate": "CANDIDATE", "repro": "REPRO",
}
_MECHANICAL_PREFIXES = ("FILE:", "CANDIDATE:", "REPRO:")


def parse_fix_md(text: str) -> dict:
    """Parse fix.md final (5 slot); ValueError menyebut SEMUA slot hilang."""
    slots: dict = {}
    missing = []
    for key, rx in _FIX_SLOT_RES.items():
        m = rx.search(text)
        if m:
            slots[key] = m.group(1).strip()
        else:
            missing.append(_FIX_SLOT_LABELS[key])
    if missing:
        raise ValueError(f"missing slots in fix.md: {', '.join(missing)}")
    slots["candidate"] = int(slots["candidate"])
    return slots


def compose_fix_md(model_part: str, candidate_file: str,
                   candidate_index: int, repro_note: str) -> str:
    """Susun fix.md final: interpretif model (WHAT CHANGED/WHY) + slot
    mekanis diisi HARNESS (pola compose_repro_md — tulisan model di slot
    mekanis dibuang & diganti fakta yang disaksikan driver)."""
    kept = [line for line in model_part.splitlines()
            if not line.startswith(_MECHANICAL_PREFIXES)]
    body = "\n".join(kept).rstrip("\n")
    return (f"{body}\n"
            f"FILE: {candidate_file}\n"
            f"CANDIDATE: {candidate_index}\n"
            f"REPRO: {repro_note}\n")
