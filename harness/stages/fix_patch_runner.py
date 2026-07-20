"""Evaluator patch tunggal stage FIX — sisi docker (dunia SEGAR).

SATU entry point untuk pre-check DONE driver DAN gate L1 (standar tunggal,
Prinsip Stabilisasi §4): evaluate_patch_in_fresh_world. Mekanisme: cek
statis pure (fix_gates) -> git apply --check di container segar -> pair 2x
via repro_sandbox_runner.run_once dengan patch model terpasang (reuse
mekanisme flip-test). repro.py yang divonis SELALU dari dir artefak beku
fase R (repro_dir) — edit model atas repro di container kerja tak
berpengaruh (spec §4).
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from harness.stages.fix_gates import (FixPatchResult, apply_failed_result,
                                      evaluate_pair_outputs,
                                      patch_static_result)
from harness.stages.repro_sandbox_runner import run_once


def check_patch_applies(image: str, patch_dir: str, patch_name: str,
                        timeout: int = 120) -> tuple[bool, str]:
    """`git apply --check` di container segar sekali pakai."""
    p = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{patch_dir}:/patch-in:ro", image,
         "bash", "-lc",
         f"cd /testbed && git apply --check /patch-in/{patch_name} 2>&1"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout)
    return p.returncode == 0, (p.stdout or "") + (p.stderr or "")


def evaluate_patch_in_fresh_world(image: str, diff_text: str,
                                  candidate_file: str, repro_dir: str,
                                  timeout: int = 300) -> FixPatchResult:
    static = patch_static_result(diff_text, candidate_file)
    if static is not None:
        return static
    tmpdir = tempfile.mkdtemp(prefix="fix-eval-")
    body = diff_text if diff_text.endswith("\n") else diff_text + "\n"
    (Path(tmpdir) / "fix.diff").write_text(body, encoding="utf-8",
                                           newline="\n")
    ok, out = check_patch_applies(image, tmpdir, "fix.diff")
    if not ok:
        return apply_failed_result(out)
    repro_host = str(Path(repro_dir).resolve())
    r1 = run_once(image, repro_host, timeout,
                  patch_host_dir=tmpdir, patch_name="fix.diff")
    r2 = run_once(image, repro_host, timeout,
                  patch_host_dir=tmpdir, patch_name="fix.diff")
    return evaluate_pair_outputs(diff_text, candidate_file,
                                 r1["output"], r1["exit"],
                                 r2["output"], r2["exit"])
