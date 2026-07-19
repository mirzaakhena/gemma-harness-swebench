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


# --- L2: ground truth = gold patch (keputusan Mirza 2026-07-19) -------------
# Vonis mekanis: file yang ditunjuk localize.md harus anggota himpunan file
# yang disentuh gold.patch (padanan flip test; gold HANYA untuk harness,
# pasca-model). Overlap rentang baris vs hunk gold = telemetri advisory —
# "gaya boleh beda", situs mekanisme tak wajib == baris hunk fix.

_DIFF_NEW_RE = re.compile(r"^\+\+\+\s+(?:b/)?(.+?)\s*$", re.MULTILINE)
_DIFF_OLD_RE = re.compile(r"^---\s+(?:a/)?(.+?)\s*$", re.MULTILINE)
_HUNK_RE = re.compile(r"^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@")


def gold_touched_files(gold_patch_text: str) -> set[str]:
    """Himpunan path file yang disentuh gold patch (sisi b/; file terhapus
    diambil dari sisi a/ karena b-nya /dev/null)."""
    files: set[str] = set()
    old_paths = _DIFF_OLD_RE.findall(gold_patch_text)
    new_paths = _DIFF_NEW_RE.findall(gold_patch_text)
    for path in new_paths:
        if path != "/dev/null":
            files.add(path)
    for path in old_paths:
        if path != "/dev/null" and path not in files:
            # pasangan +++ /dev/null (file dihapus) → pakai sisi lama
            files.add(path)
    # buang path lama yang sebenarnya punya pasangan baru (rename/normal):
    # path a/ selalu ikut ter-find; simpan hanya bila b-side-nya /dev/null.
    paired_new = set(new_paths)
    if "/dev/null" not in paired_new:
        files -= (set(old_paths) - paired_new)
    return files


def gold_line_ranges(gold_patch_text: str, target_file: str) -> list[tuple[int, int]]:
    """Rentang baris (sisi baru) hunk-hunk gold utk satu file — bahan
    telemetri overlap advisory."""
    ranges: list[tuple[int, int]] = []
    current: str | None = None
    for line in gold_patch_text.splitlines():
        m_new = re.match(r"^\+\+\+\s+(?:b/)?(.+?)\s*$", line)
        if m_new:
            current = None if m_new.group(1) == "/dev/null" else m_new.group(1)
            continue
        m_hunk = _HUNK_RE.match(line)
        if m_hunk and current == target_file:
            start = int(m_hunk.group(1))
            count = int(m_hunk.group(2) or 1)
            ranges.append((start, start + count - 1))
    return ranges


@dataclass
class LocalizeL2Result:
    file_match: bool
    line_overlap: bool | None  # None bila file salah (overlap tak bermakna)
    gold_files: set[str] = field(default_factory=set)


def evaluate_localize_l2(pointed_file: str, gold_patch_text: str,
                         lines: tuple[int, int]) -> LocalizeL2Result:
    gold_files = gold_touched_files(gold_patch_text)
    target = pointed_file.lstrip("/")
    if target not in gold_files:
        return LocalizeL2Result(file_match=False, line_overlap=None,
                                gold_files=gold_files)
    start, end = lines
    overlap = any(start <= h_end and end >= h_start
                  for h_start, h_end in gold_line_ranges(gold_patch_text,
                                                         target))
    return LocalizeL2Result(file_match=True, line_overlap=overlap,
                            gold_files=gold_files)


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
