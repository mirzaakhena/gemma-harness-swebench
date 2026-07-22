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

from harness.emit import Emitter
from harness.stages.chat_transport import INFRA_ABORT_FILENAME
from harness.stages.localize_gates import evaluate_localize_gates, parse_localize_md


def main() -> int:
    # Product gold-blind (framing Mirza 2026-07-19): gate ini murni L1.
    # Evaluasi vs gold = lapisan test-system: eval/localize_gold_eval.py.
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--rerun", type=int, required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--campaign", default="l-dev")
    ap.add_argument("--artifacts", default="../artifacts")
    args = ap.parse_args()

    em = Emitter(args.artifacts, args.campaign, args.case, args.rerun)
    md_path = em.run_dir / "files" / "localize.md"

    def log(line: str) -> None:
        with open(em.run_dir / "console.log", "a", encoding="utf-8",
                  newline="\n") as f:
            f.write(line.rstrip("\n") + "\n")

    def finish(verdict: str, failures: list[str]) -> int:
        detail = ({"gates": "ok"} if verdict == "pass"
                  else {"failures": failures})
        em.event("localize", "exit", verdict=verdict, detail=detail)
        # Lever infra-abort: bangkai infra bukan dinding LOCALIZE —
        # wall="abort" supaya statistik wall tak tercemar (KH-22).
        infra = verdict == "infra-abort"
        wall = ("abort" if infra
                else None if verdict == "pass" else "localize")
        em.write_verdict(
            phases={"localize": {"verdict": verdict, "duration_s": None}},
            wall=wall, pass_l1=(verdict == "pass"), pass_l2=None,
            infra_abort=infra)
        em.run_end(verdict={"localize": verdict}, wall=wall)
        log(f"[harness] gate localize selesai: verdict={verdict}"
            + (f" | {failures}" if failures else ""))
        print(json.dumps({"verdict": verdict, "failures": failures},
                         ensure_ascii=False))
        return 0

    # Lever infra-abort (KH-22): penanda driver dihormati SEBELUM cek
    # artefak — run crash transport/preflight bukan syntax-fail biasa.
    marker = em.run_dir / INFRA_ABORT_FILENAME
    if marker.is_file():
        try:
            reason = json.loads(marker.read_text(encoding="utf-8")
                                ).get("reason", "unknown")
        except Exception:
            reason = "unreadable infra_abort.json"
        return finish("infra-abort", [f"infra abort: {reason}"])

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
    return finish(r.verdict, r.failures)


if __name__ == "__main__":
    sys.exit(main())
