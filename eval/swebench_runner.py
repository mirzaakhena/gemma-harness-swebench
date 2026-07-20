"""Lapisan docker checker SWE-bench — container Epoch segar sekali pakai.

Pola mount /patch-in read-only mengikuti fix_patch_runner/repro_sandbox_runner.
stdout+stderr digabung: marker test di stdout, output test runner django
sering di stderr — get_logs_eval punya fallback parse seluruh isi log.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

DEFAULT_IMAGE_TPL = ("ghcr.io/epoch-research/swe-bench.eval.x86_64."
                     "{case_id}:latest")


def default_image(case_id: str) -> str:
    return DEFAULT_IMAGE_TPL.format(case_id=case_id)


def run_eval_in_container(image: str, eval_script: str, fix_diff: str,
                          test_patch: str, timeout: int = 3600) -> dict:
    tmpdir = Path(tempfile.mkdtemp(prefix="swebench-l2-"))
    for name, body in (("eval.sh", eval_script), ("fix.diff", fix_diff),
                       ("test_patch.diff", test_patch)):
        (tmpdir / name).write_text(
            body if body.endswith("\n") else body + "\n",
            encoding="utf-8", newline="\n")
    p = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{tmpdir}:/patch-in:ro", image,
         "bash", "/patch-in/eval.sh"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout)
    return {"log": (p.stdout or "") + (p.stderr or ""), "exit": p.returncode}
