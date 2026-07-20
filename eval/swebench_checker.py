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


def run_checker(case: str, rerun: int, campaign: str, artifacts: str,
                image: str, spec_path: str, timeout: int,
                runner=None) -> tuple[int, dict]:
    from datetime import datetime, timezone
    from eval.swebench_runner import run_eval_in_container
    runner = runner or run_eval_in_container
    run_dir = (Path(artifacts) / campaign / f"{campaign}--{case}--r{rerun}")
    diff_path = run_dir / "files" / "fix.diff"
    if not diff_path.is_file():
        return 1, {"error": "fix.diff not found", "run_dir": str(run_dir)}
    try:
        spec = load_spec(Path(spec_path))
    except (FileNotFoundError, ValueError) as e:
        return 1, {"error": str(e)}
    fix_diff = diff_path.read_text(encoding="utf-8")
    log_path = run_dir / "files" / "swebench_test_output.log"
    try:
        res = runner(image, build_eval_script(spec), fix_diff,
                     spec["test_patch"], timeout)
        log_path.write_text(res["log"], encoding="utf-8", newline="\n")
        raw = grade_log(spec, fix_diff, log_path)
        summary = summarize_report(
            raw, spec, case=case, rerun=rerun, image=image,
            spec_path=spec_path, log_rel="files/swebench_test_output.log",
            checked_at=datetime.now(timezone.utc).isoformat())
    except Exception as e:
        # grade_log() builds a real TestSpec via make_test_spec(), which for
        # django does a live requests.get for requirements.txt (a field
        # grading never uses) — an infra hiccup shouldn't crash mid-run.
        # Whatever log we managed to capture is still useful for debugging;
        # swebench_eval.json is deliberately NOT written since it would be
        # misleading (no real verdict was reached).
        return 1, {"error": "swebench eval failed", "detail": str(e),
                   "case": case, "rerun": rerun}
    (run_dir / "swebench_eval.json").write_bytes(
        (json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
        .encode("utf-8"))
    return 0, summary


def main(argv: list[str] | None = None) -> int:
    import argparse
    from eval.swebench_runner import default_image
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--rerun", type=int, required=True)
    ap.add_argument("--campaign", default="f-dev")
    ap.add_argument("--artifacts", default="../artifacts")
    ap.add_argument("--image", default=None)
    ap.add_argument("--spec", default=None)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args(argv)
    rc, out = run_checker(
        case=args.case, rerun=args.rerun, campaign=args.campaign,
        artifacts=args.artifacts,
        image=args.image or default_image(args.case),
        spec_path=args.spec or f"cases/gold/{args.case}/swebench_spec.json",
        timeout=args.timeout)
    print(json.dumps(out, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    import sys
    sys.exit(main())
