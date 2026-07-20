"""Test langkah gate FIX — evaluator di-stub, artefak fixture di tmp_path.

Definisi kebenaran IDENTIK dengan pre-check driver (evaluator tunggal);
gate = lapisan terakhir yang menulis verdict (vonis milik harness)."""
import json
import sys

import harness.stages.run_fix_gates as gate
from harness.stages.fix_gates import FixPatchResult

DIFF = """diff --git a/django/db/models/enums.py b/django/db/models/enums.py
--- a/django/db/models/enums.py
+++ b/django/db/models/enums.py
@@ -1,3 +1,4 @@
+import x
"""

FIX_MD = """WHAT CHANGED: a
WHY: b
FILE: django/db/models/enums.py
CANDIDATE: 1
REPRO: PASS,PASS (frozen repro, fresh container pair)
"""

OK = FixPatchResult(ok=True, reason=None,
                    touched=("django/db/models/enums.py",),
                    status1="PASS", status2="PASS", exit1=0, exit2=0)
BAD = FixPatchResult(ok=False, reason="pair-not-pass",
                     failures=["patched fresh pair not PASS,PASS "
                               "(run1=FAIL, run2=PASS)"],
                     status1="FAIL", status2="PASS")
TMO = FixPatchResult(ok=False, reason="timeout",
                     failures=["frozen repro timed out in the patched "
                               "fresh container"])


def _setup(tmp_path, diff=DIFF, md=FIX_MD, meta=True):
    art = tmp_path / "artifacts"
    files = art / "f-dev" / "f-dev--django__django-11422--r1" / "files"
    files.mkdir(parents=True)
    if diff is not None:
        (files / "fix.diff").write_text(diff, encoding="utf-8")
    if md is not None:
        (files / "fix.md").write_text(md, encoding="utf-8")
    if meta:
        (files / "fix_run.json").write_text(json.dumps(
            {"winner_attempt": 1,
             "candidate_file": "django/db/models/enums.py"}),
            encoding="utf-8")
    return art


def _run(monkeypatch, art, result):
    monkeypatch.setattr(gate, "evaluate_patch_in_fresh_world",
                        lambda *a, **k: result)
    monkeypatch.setattr(sys, "argv", [
        "run_fix_gates.py", "--case", "django__django-11422",
        "--rerun", "1", "--image", "img",
        "--input-repro-files", "unused", "--artifacts", str(art)])
    assert gate.main() == 0
    run_dir = art / "f-dev" / "f-dev--django__django-11422--r1"
    return json.loads((run_dir / "verdict.json").read_text(encoding="utf-8"))


def test_flip_verdict_and_pass_l1(monkeypatch, tmp_path):
    v = _run(monkeypatch, _setup(tmp_path), OK)
    assert v["phases"]["fix"]["verdict"] == "flip"
    assert v["pass_l1"] is True and v["wall"] is None


def test_missing_fix_diff_is_no_flip_without_docker(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError("evaluator must not run without fix.diff")
    art = _setup(tmp_path, diff=None)
    monkeypatch.setattr(gate, "evaluate_patch_in_fresh_world", boom)
    monkeypatch.setattr(sys, "argv", [
        "run_fix_gates.py", "--case", "django__django-11422",
        "--rerun", "1", "--image", "img",
        "--input-repro-files", "unused", "--artifacts", str(art)])
    assert gate.main() == 0
    v = json.loads((art / "f-dev" / "f-dev--django__django-11422--r1"
                    / "verdict.json").read_text(encoding="utf-8"))
    assert v["phases"]["fix"]["verdict"] == "no-flip"
    assert v["wall"] == "fix" and v["pass_l1"] is False


def test_evaluator_reject_is_no_flip(monkeypatch, tmp_path):
    v = _run(monkeypatch, _setup(tmp_path), BAD)
    assert v["phases"]["fix"]["verdict"] == "no-flip"
    assert v["pass_l1"] is False


def test_timeout_reason_maps_to_timeout_verdict(monkeypatch, tmp_path):
    v = _run(monkeypatch, _setup(tmp_path), TMO)
    assert v["phases"]["fix"]["verdict"] == "timeout"


def test_malformed_fix_md_blocks_flip(monkeypatch, tmp_path):
    v = _run(monkeypatch, _setup(tmp_path, md="WHAT CHANGED: a\n"), OK)
    assert v["phases"]["fix"]["verdict"] == "no-flip"


def test_exit_event_written_once_with_verdict(monkeypatch, tmp_path):
    art = _setup(tmp_path)
    _run(monkeypatch, art, OK)
    run_dir = art / "f-dev" / "f-dev--django__django-11422--r1"
    events = [json.loads(l) for l in
              (run_dir / "events.jsonl").read_text(encoding="utf-8")
              .splitlines()]
    exits = [e for e in events if e["event"] == "exit"]
    assert len(exits) == 1
    assert exits[0]["phase"] == "fix" and exits[0]["verdict"] == "flip"
    ends = [json.loads(l) for l in
            (art / "f-dev" / "runs.jsonl").read_text(encoding="utf-8")
            .splitlines() if json.loads(l)["event"] == "end"]
    assert ends and ends[0]["verdict"] == {"fix": "flip"}
