"""Langkah gate harness untuk stage FIX (dipakai untuk SEMUA model).

Definisi kebenaran IDENTIK dengan pre-check driver — evaluator tunggal
evaluate_patch_in_fresh_world (spec §7, Prinsip Stabilisasi §4): fix.diff
non-empty & apply bersih, hanya menyentuh file kandidat, repro beku pair 2x
PASS di dunia segar, format fix.md sah. Gate = lapisan terakhir yang
menulis verdict (event exit + verdict.json + runs.jsonl end). Product
gold-blind murni — evaluasi vs gold hidup di eval/fix_gold_eval.py.

Pemakaian (dari root main):
    python harness/stages/run_fix_gates.py --case <case_id> --rerun <N>
        --image <img> --input-repro-files <dir files run R>
        [--campaign f-dev] [--artifacts ../artifacts]
"""
from __future__ import annotations

import argparse
import json
import sys

from harness.emit import Emitter
from harness.stages.fix_gates import parse_fix_md
from harness.stages.fix_patch_runner import evaluate_patch_in_fresh_world


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--rerun", type=int, required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--input-repro-files", required=True,
                    help="dir files/ run REPRODUCE qualified (repro.py beku)")
    ap.add_argument("--campaign", default="f-dev")
    ap.add_argument("--artifacts", default="../artifacts")
    args = ap.parse_args()

    em = Emitter(args.artifacts, args.campaign, args.case, args.rerun)
    files_dir = em.run_dir / "files"

    def log(line: str) -> None:
        with open(em.run_dir / "console.log", "a", encoding="utf-8",
                  newline="\n") as f:
            f.write(line.rstrip("\n") + "\n")

    def finish(verdict: str, failures: list[str],
               extra: dict | None = None) -> int:
        detail = ({"gates": "ok"} if verdict == "flip"
                  else {"failures": failures})
        if extra:
            detail.update(extra)
        em.event("fix", "exit", verdict=verdict, detail=detail)
        wall = None if verdict == "flip" else "fix"
        em.write_verdict(
            phases={"fix": {"verdict": verdict, "duration_s": None}},
            wall=wall, pass_l1=(verdict == "flip"), pass_l2=None)
        em.run_end(verdict={"fix": verdict}, wall=wall)
        log(f"[harness] gate fix selesai: verdict={verdict}"
            + (f" | {failures}" if failures else ""))
        print(json.dumps({"verdict": verdict, "failures": failures},
                         ensure_ascii=False))
        return 0

    diff_path = files_dir / "fix.diff"
    md_path = files_dir / "fix.md"
    meta_path = files_dir / "fix_run.json"

    if not diff_path.is_file():
        return finish("no-flip",
                      ["required artifact missing: fix.diff "
                       "(no winning attempt)"])
    if not meta_path.is_file():
        return finish("no-flip", ["required artifact missing: fix_run.json"])
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    candidate_file = meta.get("candidate_file")
    if not candidate_file:
        return finish("no-flip",
                      ["fix_run.json has no winning candidate_file"])

    md_failures: list[str] = []
    if not md_path.is_file():
        md_failures.append("required artifact missing: fix.md")
    else:
        try:
            parse_fix_md(md_path.read_text(encoding="utf-8"))
        except ValueError as e:
            md_failures.append(f"fix.md format: {e}")

    r = evaluate_patch_in_fresh_world(
        args.image, diff_path.read_text(encoding="utf-8"),
        candidate_file, args.input_repro_files)
    pair = {"status1": r.status1, "status2": r.status2,
            "exit1": r.exit1, "exit2": r.exit2}
    (em.run_dir / "gate_runs.json").write_text(
        json.dumps({"reason": r.reason, "failures": r.failures,
                    "pair": pair}, ensure_ascii=False),
        encoding="utf-8", newline="\n")

    if r.reason == "timeout":
        return finish("timeout", r.failures, {"pair": pair})
    if r.ok and not md_failures:
        return finish("flip", [], {"pair": pair})
    return finish("no-flip", md_failures + r.failures, {"pair": pair})


if __name__ == "__main__":
    sys.exit(main())
