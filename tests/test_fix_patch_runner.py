"""Test evaluator patch tunggal di dunia segar — docker di-stub
(monkeypatch atribut modul, pola test_localize_driver)."""
from harness.stages import fix_patch_runner as fpr

DIFF = """diff --git a/django/db/models/enums.py b/django/db/models/enums.py
--- a/django/db/models/enums.py
+++ b/django/db/models/enums.py
@@ -60,7 +60,13 @@ def values(cls):
+    def __str__(self):
+        return str(self.value)
"""

CAND = "django/db/models/enums.py"


def _no_docker(monkeypatch, what):
    def boom(*a, **k):
        raise AssertionError(f"{what} must not run")
    return boom


def test_static_reject_short_circuits_all_docker(monkeypatch):
    monkeypatch.setattr(fpr, "check_patch_applies",
                        _no_docker(monkeypatch, "apply-check"))
    monkeypatch.setattr(fpr, "run_once", _no_docker(monkeypatch, "pair run"))
    r = fpr.evaluate_patch_in_fresh_world("img", "", CAND, "/tmp/x")
    assert r.ok is False and r.reason == "empty-diff"


def test_apply_failed_short_circuits_pair(monkeypatch):
    monkeypatch.setattr(fpr, "check_patch_applies",
                        lambda *a, **k: (False,
                                         "error: patch failed: enums.py:60"))
    monkeypatch.setattr(fpr, "run_once", _no_docker(monkeypatch, "pair run"))
    r = fpr.evaluate_patch_in_fresh_world("img", DIFF, CAND, "/tmp/x")
    assert r.reason == "apply-failed"
    assert "patch failed" in r.failures[0]


def test_pair_runs_twice_with_model_patch(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(fpr, "check_patch_applies", lambda *a, **k: (True, ""))

    def fake_run_once(image, repro_dir, timeout,
                      patch_host_dir=None, patch_name=None):
        calls.append((image, repro_dir, patch_host_dir, patch_name))
        return {"output": "REPRO_STATUS: PASS\n", "exit": 0}

    monkeypatch.setattr(fpr, "run_once", fake_run_once)
    r = fpr.evaluate_patch_in_fresh_world("img", DIFF, CAND, str(tmp_path))
    assert r.ok is True
    assert len(calls) == 2
    assert all(c[3] == "fix.diff" for c in calls)       # patch model dipasang
    assert calls[0][1] == str(tmp_path.resolve())       # repro dari dir BEKU


def test_pair_not_pass_bubbles_structured_result(monkeypatch, tmp_path):
    monkeypatch.setattr(fpr, "check_patch_applies", lambda *a, **k: (True, ""))
    outs = iter([{"output": "REPRO_STATUS: PASS\n", "exit": 0},
                 {"output": "boom\n", "exit": 1}])
    monkeypatch.setattr(fpr, "run_once", lambda *a, **k: next(outs))
    r = fpr.evaluate_patch_in_fresh_world("img", DIFF, CAND, str(tmp_path))
    assert r.ok is False and r.reason == "pair-not-pass"
    assert r.status1 == "PASS" and r.status2 is None
    assert r.exit2 == 1 and "boom" in r.run2_tail


def test_check_patch_applies_command_shape(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd

        class P:
            returncode = 0
            stdout = ""
            stderr = ""
        return P()

    monkeypatch.setattr(fpr.subprocess, "run", fake_run)
    ok, out = fpr.check_patch_applies("img", str(tmp_path), "fix.diff")
    assert ok is True
    assert "git apply --check /patch-in/fix.diff" in seen["cmd"][-1]
    assert f"{tmp_path}:/patch-in:ro" in seen["cmd"]
    assert "--rm" in seen["cmd"]
