"""Langkah gate harness untuk stage REPRODUCE (dipakai untuk SEMUA model).

Jalankan files/repro.py milik sebuah run di 2 container docker segar
(repro_sandbox_runner), evaluasi 4 gate (reproduce_gates.evaluate_gates),
lalu tulis vonis resmi: event `exit`, verdict.json, runs.jsonl end.

Pemakaian (dari root main\\):
    python harness/stages/run_repro_gates.py --case <case_id> --rerun <N> \\
        --image <img> [--campaign r-dev] [--artifacts ../artifacts]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from harness.emit import Emitter
from harness.stages.reproduce_gates import evaluate_gates


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--rerun", type=int, required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--campaign", default="r-dev")
    ap.add_argument("--artifacts", default="../artifacts")
    args = ap.parse_args()

    em = Emitter(args.artifacts, args.campaign, args.case, args.rerun)
    files_dir = em.run_dir / "files"
    repro_py = files_dir / "repro.py"
    repro_md_path = files_dir / "repro.md"

    def log(line: str) -> None:
        with open(em.run_dir / "console.log", "a", encoding="utf-8",
                  newline="\n") as f:
            f.write(line.rstrip("\n") + "\n")

    def finish(verdict: str, failures: list[str]) -> int:
        detail = ({"gates": "4/4 ok"} if verdict == "pass"
                  else {"failures": failures})
        em.event("reproduce", "exit", verdict=verdict, detail=detail)
        wall = None if verdict == "pass" else "reproduce"
        em.write_verdict(
            phases={"reproduce": {"verdict": verdict, "duration_s": None}},
            wall=wall, pass_l1=None, pass_l2=None)
        em.run_end(verdict={"reproduce": verdict}, wall=wall)
        log(f"[harness] gate selesai: verdict={verdict}"
            + (f" | {failures}" if failures else ""))
        print(json.dumps({"verdict": verdict, "failures": failures},
                         ensure_ascii=False))
        return 0

    if not repro_py.is_file() or not repro_md_path.is_file():
        missing = [p.name for p in (repro_py, repro_md_path) if not p.is_file()]
        return finish("syntax-fail", [f"artefak wajib tidak ada: {missing}"])

    runner = Path(__file__).with_name("repro_sandbox_runner.py")
    p = subprocess.run(
        [sys.executable, str(runner), "--image", args.image,
         "--repro", str(repro_py), "--runs", "2"],
        capture_output=True, text=True, encoding="utf-8")
    data = json.loads(p.stdout)
    (em.run_dir / "gate_runs.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8", newline="\n")
    runs = data["runs"]

    r = evaluate_gates(
        repro_md_text=repro_md_path.read_text(encoding="utf-8"),
        fresh_run1_output=runs[0]["output"], fresh_run1_exit=runs[0]["exit"],
        fresh_run2_output=runs[1]["output"], fresh_run2_exit=runs[1]["exit"])
    return finish(r.verdict, r.failures)


if __name__ == "__main__":
    sys.exit(main())
