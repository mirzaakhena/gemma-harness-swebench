"""SWE-bench checker (L2) — eval realm-dev, penghasil vonis `resolved`.

Spec: docs/superpowers/specs/2026-07-20-swebench-checker-l2-design.md.
Vonis via grading RESMI paket swebench (get_eval_report); eksekusi test di
container Epoch segar (lapisan docker: eval/swebench_runner.py, Task 5;
CLI: Task 6). Hasil ke swebench_eval.json — TIDAK menyentuh verdict.json /
events.jsonl; tidak pernah diumpankan ke loop model (boundary integritas).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from textwrap import dedent

from eval._swebench_compat import ensure_resource_shim

REQUIRED_KEYS = ("instance_id", "repo", "version", "base_commit",
                 "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS")


def load_spec(spec_path: Path) -> dict:
    p = Path(spec_path)
    if not p.is_file():
        raise FileNotFoundError(
            f"swebench_spec.json not found: {p} — run "
            f"`python -m eval.fetch_swebench_spec --case <case_id>` first")
    spec = json.loads(p.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_KEYS if k not in spec]
    if missing:
        raise ValueError(f"swebench_spec.json missing keys: {missing}")
    return spec


def build_eval_script(spec: dict) -> str:
    """Bash utk container Epoch segar: fix.diff model → test_patch resmi →
    test F2P∪P2P ber-marker (pola inspect_evals, terbukti utk image Epoch).
    Gagal apply fix → exit 2 tanpa marker (grading: applied=False)."""
    ensure_resource_shim()
    from swebench.harness.constants import (APPLY_PATCH_FAIL,
                                            END_TEST_OUTPUT,
                                            MAP_REPO_VERSION_TO_SPECS,
                                            RESET_FAILED,
                                            START_TEST_OUTPUT)
    from swebench.harness.test_spec.python import get_test_directives
    specs = MAP_REPO_VERSION_TO_SPECS[spec["repo"]][spec["version"]]
    test_cmd = specs["test_cmd"]
    if isinstance(test_cmd, list):
        test_cmd = test_cmd[-1]
    tp_files = re.findall(r"--- a/(.*)", spec["test_patch"])
    directives = get_test_directives({"repo": spec["repo"],
                                      "test_patch": spec["test_patch"]})
    nl = "\n"
    return dedent(f"""\
        #!/bin/bash
        set -uo pipefail -x
        cd /testbed
        set +x
        source /opt/miniconda3/bin/activate
        conda activate testbed
        set -x
        {nl.join(specs.get("eval_commands", []))}
        cd /testbed
        {specs.get("install", "")}
        git apply --check /patch-in/fix.diff || {{ echo FIX_APPLY_FAILED; exit 2; }}
        git apply /patch-in/fix.diff
        git checkout {spec["base_commit"]} {" ".join(tp_files)} || {{ echo '{RESET_FAILED}'; exit 3; }}
        git apply /patch-in/test_patch.diff || {{ echo '{APPLY_PATCH_FAIL}'; exit 4; }}
        set +x
        echo '{START_TEST_OUTPUT}'
        {test_cmd} {" ".join(directives)}
        echo '{END_TEST_OUTPUT}'
    """)


def grade_log(spec: dict, fix_diff_text: str, log_path: Path) -> dict:
    """Vonis resmi host-side: log parser per-repo + get_eval_report."""
    ensure_resource_shim()
    from swebench.harness.constants import KEY_INSTANCE_ID, KEY_PREDICTION
    from swebench.harness.grading import get_eval_report
    from swebench.harness.test_spec.test_spec import make_test_spec
    prediction = {KEY_INSTANCE_ID: spec["instance_id"],
                  KEY_PREDICTION: fix_diff_text,
                  "model_name_or_path": "gemma-harness"}
    return get_eval_report(make_test_spec(dict(spec)), prediction,
                           str(log_path),
                           include_tests_status=True)[spec["instance_id"]]


def summarize_report(raw: dict, spec: dict, case: str, rerun: int,
                     image: str, spec_path: str, log_rel: str,
                     checked_at: str) -> dict:
    """Skema swebench_eval.json (spec §5) — KAYA: regresi per nama test."""
    tests = raw.get("tests_status") or {}
    f2p = tests.get("FAIL_TO_PASS") or {"success": [], "failure": []}
    p2p = tests.get("PASS_TO_PASS") or {"success": [], "failure": []}
    return {"case": case, "rerun": rerun,
            "resolved": bool(raw.get("resolved")),
            "patch_successfully_applied":
                bool(raw.get("patch_successfully_applied")),
            "f2p_passed": list(f2p.get("success", [])),
            "f2p_failed": list(f2p.get("failure", [])),
            "p2p_passed_count": len(p2p.get("success", [])),
            "p2p_failed": list(p2p.get("failure", [])),
            "image": image, "spec": spec_path, "log": log_rel,
            "checked_at": checked_at}
