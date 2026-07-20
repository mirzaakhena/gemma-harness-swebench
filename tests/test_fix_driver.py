"""Test driver FIX — helper: input beku, seed per-attempt, diff collector.

Spec 2026-07-20 §3: seed = problem + repro.md verbatim + ISI repro.py
(pelajaran P21) + kandidat AKTIF SAJA (anti context-pollution).
"""
from pathlib import Path

import harness.stages.run_fix_gemma as drv

CANDS = """CANDIDATE 1
file: django/db/models/enums.py
evidence: builds the label from name instead of value
expectation: str() on a choice returns its value
CANDIDATE 2
file: django/db/models/fields/__init__.py
evidence: renders the stored label downstream
expectation: display uses the right value
"""

REPRO_MD = """SYMPTOM: str() of a choice renders the enum name
TRIGGER: access str(MyChoices.FIRST) on a TextChoices member
EXPECTED vs ACTUAL:
EXPECTED: the raw value
ACTUAL: the enum label
REPRO COMMAND: python /testbed/.pipe/repro.py
CONFIRMED-AT-BASE: yes
"""


def _mkinputs(tmp_path):
    loc = tmp_path / "loc"
    rep = tmp_path / "rep"
    loc.mkdir()
    rep.mkdir()
    (loc / "candidates.md").write_text(CANDS, encoding="utf-8")
    (rep / "repro.md").write_text(REPRO_MD, encoding="utf-8")
    (rep / "repro.py").write_text("print('REPRO_STATUS: FAIL')\n",
                                  encoding="utf-8")
    return loc, rep


def test_load_fix_inputs_reads_frozen_artifacts(tmp_path):
    loc, rep = _mkinputs(tmp_path)
    inputs = drv.load_fix_inputs(loc, rep)
    assert [c["file"] for c in inputs.candidates] == [
        "django/db/models/enums.py", "django/db/models/fields/__init__.py"]
    assert inputs.candidates[0]["evidence"].startswith("builds")
    assert "SYMPTOM" in inputs.repro_md
    assert "REPRO_STATUS" in inputs.repro_py


def test_seed_contains_active_candidate_only(tmp_path):
    loc, rep = _mkinputs(tmp_path)
    inputs = drv.load_fix_inputs(loc, rep)
    seed = drv.compose_fix_seed("problem text", inputs.repro_md,
                                inputs.repro_py, inputs.candidates[0])
    assert "problem text" in seed
    assert "django/db/models/enums.py" in seed
    # anti context-pollution: kandidat lain TIDAK pernah disebut
    assert "django/db/models/fields/__init__.py" not in seed
    assert "YOUR EDIT SITE" in seed
    assert "print('REPRO_STATUS: FAIL')" in seed  # isi repro.py ikut (P21)
    assert "SYMPTOM" in seed                      # repro.md verbatim


def test_seed_is_english(tmp_path):
    loc, rep = _mkinputs(tmp_path)
    inputs = drv.load_fix_inputs(loc, rep)
    seed = drv.compose_fix_seed("p", inputs.repro_md, inputs.repro_py,
                                inputs.candidates[1])
    for word in ("Belum", "kamu", "dulu", "serahkan", "jalankan"):
        assert word not in seed


def test_collect_work_diff_uses_git_add_n_excluding_pipe(monkeypatch):
    calls = []

    def fake_exec(container, cmd, timeout=180):
        calls.append(cmd)
        return "diff --git a/x b/x\n", 0

    monkeypatch.setattr(drv, "docker_exec", fake_exec)
    out = drv.collect_work_diff("c1")
    assert out.startswith("diff --git")
    assert "git add -N" in calls[0]   # file baru ter-cover (kontrak §10)
    assert ".pipe" in calls[0]        # workspace probe tidak masuk diff
    assert "git diff" in calls[0]


def test_collect_work_diff_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(drv, "docker_exec",
                        lambda *a, **k: ("fatal: not a git repo", 128))
    assert drv.collect_work_diff("c1") == ""


def test_protocol_note_names_fix_actions():
    assert "```bash" in drv.PROTOCOL_NOTE
    assert "```fix.md" in drv.PROTOCOL_NOTE
    assert "DONE" in drv.PROTOCOL_NOTE
    assert "REPRO_STATUS: PASS" in drv.PROTOCOL_NOTE


# --- e2e kering main(): loop kandidat, pre-check, artefak, events -----------
# Docker/chat/evaluator di-stub; tanpa Gemma & docker nyata.

import json
import subprocess
import sys

from harness.stages.fix_gates import FixPatchResult

DIFF = """diff --git a/django/db/models/enums.py b/django/db/models/enums.py
--- a/django/db/models/enums.py
+++ b/django/db/models/enums.py
@@ -60,4 +60,8 @@ class Choices:
+    def __str__(self):
+        return str(self.value)
"""

R_BASH = "```bash\npython /testbed/.pipe/repro.py\n```"
R_DONE = ("```fix.md\nWHAT CHANGED: added __str__ returning the value.\n"
          "WHY: str() now renders the raw value.\n```\nDONE")

OK1 = FixPatchResult(ok=True, reason=None,
                     touched=("django/db/models/enums.py",),
                     status1="PASS", status2="PASS", exit1=0, exit2=0)
BAD = FixPatchResult(ok=False, reason="pair-not-pass",
                     failures=["patched fresh pair not PASS,PASS "
                               "(run1=FAIL, run2=PASS)"],
                     touched=("django/db/models/enums.py",),
                     status1="FAIL", status2="PASS", exit1=1, exit2=0,
                     run1_tail="REPRO_STATUS: FAIL", run2_tail="ok")


def _run_main(monkeypatch, tmp_path, replies, eval_results, max_turns=3):
    loc, rep = _mkinputs(tmp_path)
    problem = tmp_path / "problem.txt"
    problem.write_text("the bug", encoding="utf-8")
    art = tmp_path / "artifacts"
    reply_iter = iter(replies)
    monkeypatch.setattr(drv, "chat", lambda *a, **k: next(reply_iter))

    def fake_exec(container, cmd, timeout=180):
        if "repro.py" in cmd:
            return "REPRO_STATUS: PASS\n", 0
        if "git diff" in cmd:
            return DIFF, 0
        return "", 0

    monkeypatch.setattr(drv, "docker_exec", fake_exec)
    monkeypatch.setattr(drv, "docker_write_file", lambda *a, **k: None)
    monkeypatch.setattr(drv.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0,
                                                                    "", ""))
    result_iter = iter(eval_results)
    monkeypatch.setattr(drv, "evaluate_patch_in_fresh_world",
                        lambda *a, **k: next(result_iter))
    monkeypatch.setattr(sys, "argv", [
        "run_fix_gemma.py", "--case", "django__django-11422", "--rerun", "1",
        "--image", "img", "--input-localize-files", str(loc),
        "--input-repro-files", str(rep), "--problem-file", str(problem),
        "--artifacts", str(art), "--max-turns", str(max_turns)])
    assert drv.main() == 0
    return art / "f-dev" / "f-dev--django__django-11422--r1"


def _events(run_dir):
    return [json.loads(l) for l in
            (run_dir / "events.jsonl").read_text(encoding="utf-8")
            .splitlines()]


def test_first_candidate_wins(monkeypatch, tmp_path):
    run = _run_main(monkeypatch, tmp_path, [R_BASH, R_DONE], [OK1])
    files = run / "files"
    assert (files / "fix.diff").read_text(encoding="utf-8").startswith(
        "diff --git")
    fix_md = (files / "fix.md").read_text(encoding="utf-8")
    assert "FILE: django/db/models/enums.py" in fix_md
    assert "CANDIDATE: 1" in fix_md
    assert "WHAT CHANGED: added __str__" in fix_md
    assert (files / "attempts" / "attempt-1.diff").is_file()
    meta = json.loads((files / "fix_run.json").read_text(encoding="utf-8"))
    assert meta["winner_attempt"] == 1
    assert meta["candidate_file"] == "django/db/models/enums.py"
    events = _events(run)
    assert [e for e in events if e["event"] == "enter"
            and e["phase"] == "fix"]
    assert not [e for e in events if e["event"] == "exit"]  # vonis milik gate
    assert (files / "input-candidates.md").is_file()


def test_failed_precheck_iterates_to_next_candidate(monkeypatch, tmp_path):
    # attempt 1: PASS disaksikan, DONE, tapi pre-check gagal; budget habis;
    # attempt 2 (kandidat berikutnya, sesi fresh): menang.
    replies = [R_BASH, R_DONE, "still thinking", R_BASH, R_DONE]
    OK2 = FixPatchResult(ok=True, reason=None,
                         touched=("django/db/models/fields/__init__.py",),
                         status1="PASS", status2="PASS", exit1=0, exit2=0)
    run = _run_main(monkeypatch, tmp_path, replies, [BAD, OK2])
    meta = json.loads((run / "files" / "fix_run.json")
                      .read_text(encoding="utf-8"))
    assert meta["winner_attempt"] == 2
    assert meta["attempts"][0]["result"] == "exhausted"
    assert meta["attempts"][1]["result"] == "win"
    assert (run / "files" / "attempts" / "attempt-1.diff").is_file()
    retries = [e for e in _events(run) if e["event"] == "retry"]
    precheck = [e for e in retries
                if "pre-check" in e["detail"].get("why", "")]
    assert precheck and precheck[0]["attempt"] == 1
    assert precheck[0]["detail"]["pair"]["status1"] == "FAIL"
    exhausted = [e for e in retries
                 if "exhausted" in e["detail"].get("why", "")]
    assert exhausted and exhausted[0]["attempt"] == 1


def test_done_without_witnessed_pass_rejected(monkeypatch, tmp_path):
    # DONE tanpa pernah menjalankan repro -> ditolak; evaluator TIDAK pernah
    # dipanggil (eval_results kosong: satu panggilan saja meledak
    # StopIteration -> jalur abort -> assert main()==0 di _run_main gagal);
    # dua kandidat habis -> winner None.
    replies = [R_DONE, "prose", "prose", R_DONE, "prose", "prose"]
    loc_rep_run = _run_main(monkeypatch, tmp_path, replies, [])
    meta = json.loads((loc_rep_run / "files" / "fix_run.json")
                      .read_text(encoding="utf-8"))
    assert meta["winner_attempt"] is None
    rejected = [e for e in _events(loc_rep_run) if e["event"] == "retry"
                and "done-rejected" in e["detail"].get("why", "")]
    assert rejected
    assert "REPRO_STATUS: PASS" in rejected[0]["detail"]["why"]
    assert not (loc_rep_run / "verdict.json").is_file()  # vonis milik gate
