"""Evaluasi gold FIX — lapisan test-system (dev-only), product gold-blind.

Penangkap false-PASS (spec §8): run yang flip secara product tapi patch-nya
menyentuh file / arah yang berbeda dari gold (mis. special-casing repro).
Dijalankan MANUAL oleh pengembang setelah gate product selesai:

    python eval/fix_gold_eval.py --case <case_id> --rerun <N>
        --gold cases/gold/<case_id>/gold.patch [--campaign f-dev]
        [--artifacts ../artifacts]

Output: gold_eval.json di run dir + JSON ke stdout. TIDAK menyentuh
events.jsonl / verdict.json — hasilnya tidak pernah diumpankan ke loop
model (boundary integritas).

file_match = file yang disentuh fix.diff ⊆ file gold (subset, bukan ==,
karena gold patch lazim ikut menyentuh test file yang memang bukan urusan
model — padanan kriteria shortlist LOCALIZE). line_overlap = irisan rentang
hunk (sisi baru) fix.diff vs gold — ADVISORY (gaya boleh beda, ala flip
test), None bila file_match False.

R15 (LV-14, detektor dua-arah region-hunk): line_overlap menyesatkan dua
arah (11999 superset overlap=true; 12907 rewrite overlap=false) — keduanya
berhenti di lokasi, tak pernah menyentuh bentuk. Per file yang disentuh
patch: hitung jumlah region hunk gold vs fix; `region_mismatch` per file
("subset" = fix<gold, "superset" = fix>gold); `region_flag` = ada mismatch
DAN line_overlap=true (kelas hijau-longgar — overlap merah sudah advisory
sendiri). File gold yang tak disentuh patch (test file resmi) tidak
dihitung — semantik subset file_match. BATAS terdokumentasi (12284):
divergensi DI DALAM satu region (jumlah region sama) tidak terlihat —
`region_flag=False` BUKAN "patch setara gold"; intra-hunk tetap butuh
bacaan diff (§3b). Label-only: papan skor & autopsi, bukan loop model.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.localize_gold_eval import gold_line_ranges, gold_touched_files


def evaluate_fix_gold(fix_diff_text: str, gold_patch_text: str) -> dict:
    touched = sorted(gold_touched_files(fix_diff_text))
    gold_files = sorted(gold_touched_files(gold_patch_text))
    file_match = bool(touched) and set(touched) <= set(gold_files)
    line_overlap: bool | None = None
    # R15: jumlah region hunk per file (dua-arah); None bila file salah,
    # konsisten dgn line_overlap.
    hunk_regions: dict[str, dict[str, int]] | None = None
    region_mismatch: dict[str, str] | None = None
    region_flag: bool | None = None
    if file_match:
        line_overlap = False
        hunk_regions = {}
        region_mismatch = {}
        for f in touched:
            gold_ranges = gold_line_ranges(gold_patch_text, f)
            fix_ranges = gold_line_ranges(fix_diff_text, f)
            for start, end in fix_ranges:
                if any(start <= g_end and end >= g_start
                       for g_start, g_end in gold_ranges):
                    line_overlap = True
            hunk_regions[f] = {"gold": len(gold_ranges),
                               "fix": len(fix_ranges)}
            if len(fix_ranges) < len(gold_ranges):
                region_mismatch[f] = "subset"
            elif len(fix_ranges) > len(gold_ranges):
                region_mismatch[f] = "superset"
        # Flag khusus kelas hijau-longgar: overlap merah sudah advisory
        # sendiri. BATAS (12284): region sama != patch setara gold.
        region_flag = bool(region_mismatch) and line_overlap is True
    return {"touched_files": touched, "gold_files": gold_files,
            "file_match": file_match, "line_overlap": line_overlap,
            "hunk_regions": hunk_regions,
            "region_mismatch": region_mismatch,
            "region_flag": region_flag}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--rerun", type=int, required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--campaign", default="f-dev")
    ap.add_argument("--artifacts", default="../artifacts")
    args = ap.parse_args()

    run_dir = (Path(args.artifacts) / args.campaign
               / f"{args.campaign}--{args.case}--r{args.rerun}")
    diff_path = run_dir / "files" / "fix.diff"
    if not diff_path.is_file():
        print(json.dumps({"error": "fix.diff not found",
                          "run_dir": str(run_dir)}))
        return 1

    result = {"case": args.case, "rerun": args.rerun,
              **evaluate_fix_gold(
                  diff_path.read_text(encoding="utf-8"),
                  Path(args.gold).read_text(encoding="utf-8"))}
    (run_dir / "gold_eval.json").write_bytes(
        (json.dumps(result, ensure_ascii=False, indent=1) + "\n")
        .encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
