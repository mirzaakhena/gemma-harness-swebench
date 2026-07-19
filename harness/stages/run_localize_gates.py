"""Langkah gate harness untuk stage LOCALIZE (dipakai untuk SEMUA model).

Baca files/localize.md sebuah run, cek keberadaan + panjang file yang ditunjuk
di container docker segar, evaluasi gate (localize_gates), tulis vonis resmi:
event `exit`, verdict.json, runs.jsonl end.

Pemakaian (dari root main):
    python harness/stages/run_localize_gates.py --case <case_id> --rerun <N>
        --image <img> [--campaign l-dev] [--artifacts ../artifacts]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from pathlib import Path

from harness.emit import Emitter
from harness.stages.localize_gates import (
    evaluate_localize_gates,
    evaluate_localize_l2,
    parse_localize_md,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--rerun", type=int, required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--campaign", default="l-dev")
    ap.add_argument("--artifacts", default="../artifacts")
    ap.add_argument("--gold", default=None,
                    help="path gold.patch (host) — L2: file yang ditunjuk "
                         "harus file yang disentuh gold; HANYA harness, "
                         "pasca-model")
    args = ap.parse_args()

    em = Emitter(args.artifacts, args.campaign, args.case, args.rerun)
    md_path = em.run_dir / "files" / "localize.md"

    def log(line: str) -> None:
        with open(em.run_dir / "console.log", "a", encoding="utf-8",
                  newline="\n") as f:
            f.write(line.rstrip("\n") + "\n")

    def finish(verdict: str, failures: list[str],
               l2: dict | None = None, pass_l2: bool | None = None) -> int:
        detail = ({"gates": "ok"} if verdict == "pass"
                  else {"failures": failures})
        if l2 is not None:
            detail["l2"] = l2
        em.event("localize", "exit", verdict=verdict, detail=detail)
        wall = None if verdict == "pass" else "localize"
        em.write_verdict(
            phases={"localize": {"verdict": verdict, "duration_s": None}},
            wall=wall, pass_l1=(verdict == "pass"), pass_l2=pass_l2)
        em.run_end(verdict={"localize": verdict}, wall=wall)
        log(f"[harness] gate localize selesai: verdict={verdict}"
            + (f" | {failures}" if failures else ""))
        print(json.dumps({"verdict": verdict, "failures": failures,
                          "l2": l2}, ensure_ascii=False))
        return 0

    if not md_path.is_file():
        return finish("syntax-fail", ["artefak wajib tidak ada: localize.md"])
    md_text = md_path.read_text(encoding="utf-8")

    file_exists = False
    line_count = None
    try:
        slots = parse_localize_md(md_text)
        target = slots["file"].lstrip("/")
        p = subprocess.run(
            ["docker", "run", "--rm", args.image, "bash", "-lc",
             f"test -f '/testbed/{target}' && wc -l < '/testbed/{target}'"],
            capture_output=True, text=True, encoding="utf-8", timeout=120)
        if p.returncode == 0:
            file_exists = True
            line_count = int(p.stdout.strip())
    except ValueError:
        pass  # format salah — evaluate_localize_gates yang memvonis
    r = evaluate_localize_gates(md_text, file_exists=file_exists,
                                file_line_count=line_count)
    if r.verdict != "pass" or args.gold is None:
        return finish(r.verdict, r.failures)

    # L1 pass + gold tersedia → L2: file yang ditunjuk vs file gold.
    gold_text = Path(args.gold).read_text(encoding="utf-8")
    slots = parse_localize_md(md_text)
    l2 = evaluate_localize_l2(slots["file"], gold_text, lines=slots["lines"])
    l2_detail = {"file_match": l2.file_match,
                 "line_overlap": l2.line_overlap,
                 "gold_files": sorted(l2.gold_files)}
    if not l2.file_match:
        return finish(
            "wrong-logic",
            [f"L2 failed: pointed file {slots['file']!r} is not touched by "
             f"the gold fix (gold touches: {sorted(l2.gold_files)})"],
            l2=l2_detail, pass_l2=False)
    return finish("pass", [], l2=l2_detail, pass_l2=True)


if __name__ == "__main__":
    sys.exit(main())
