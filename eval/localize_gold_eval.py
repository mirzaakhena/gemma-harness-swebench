"""Evaluasi gold LOCALIZE — lapisan test-system (dev-only), product gold-blind.

Ground truth kebenaran LOCALIZE = himpunan file yang disentuh gold patch
(keputusan Mirza 2026-07-19; padanan flip test REPRODUCE). Script ini
dijalankan MANUAL oleh pengembang setelah gate product selesai:

    python eval/localize_gold_eval.py --case <case_id> --rerun <N>
        --gold cases/gold/<case_id>/gold.patch [--campaign l-dev]
        [--artifacts ../artifacts]

Output: `gold_eval.json` di run dir (di samping flip_run.json-nya REPRODUCE)
+ JSON ke stdout. TIDAK menyentuh events.jsonl / verdict.json — vonis
product tetap L1 murni; qualified dev-loop dibaca dari file ini.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

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
            files.add(path)
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


def shortlist_qualified(candidate_files: list[str] | None, pointed_file: str,
                        gold_files: set[str]) -> tuple[bool, str]:
    """Kriteria qualified LOCALIZE (keputusan Mirza 2026-07-19 via buttons):
    ada kandidat ∈ file gold — fase FIX mengiterasi shortlist, yang penting
    jawaban benar masuk daftar pendek (pagar 2-3 kandidat di gate driver).
    Fallback run era pra-candidates: chosen file (ditandai criterion)."""
    if candidate_files is None:
        return pointed_file.lstrip("/") in gold_files, "chosen-file-v1"
    return (any(f.lstrip("/") in gold_files for f in candidate_files),
            "shortlist-v2")


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


def main() -> int:
    from harness.stages.localize_gates import parse_localize_md

    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--rerun", type=int, required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--campaign", default="l-dev")
    ap.add_argument("--artifacts", default="../artifacts")
    args = ap.parse_args()

    run_dir = (Path(args.artifacts) /
               args.campaign / f"{args.campaign}--{args.case}--r{args.rerun}")
    md_path = run_dir / "files" / "localize.md"
    if not md_path.is_file():
        print(json.dumps({"error": "localize.md not found",
                          "run_dir": str(run_dir)}))
        return 1

    slots = parse_localize_md(md_path.read_text(encoding="utf-8"))
    gold_text = Path(args.gold).read_text(encoding="utf-8")
    r = evaluate_localize_l2(slots["file"], gold_text, lines=slots["lines"])

    cand_path = run_dir / "files" / "candidates.md"
    candidate_files: list[str] | None = None
    if cand_path.is_file():
        from harness.stages.localize_gates import parse_candidates_md
        candidate_files = [c["file"] for c in
                           parse_candidates_md(
                               cand_path.read_text(encoding="utf-8"))]
    qualified, criterion = shortlist_qualified(candidate_files,
                                               slots["file"], r.gold_files)
    result = {
        "case": args.case,
        "rerun": args.rerun,
        "pointed_file": slots["file"],
        "pointed_lines": list(slots["lines"]),
        "candidate_files": candidate_files,
        "gold_files": sorted(r.gold_files),
        "file_match": r.file_match,
        "line_overlap": r.line_overlap,
        "criterion": criterion,
        "qualified": qualified,
    }
    out_path = run_dir / "gold_eval.json"
    out_path.write_bytes(
        (json.dumps(result, ensure_ascii=False, indent=1) + "\n")
        .encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
