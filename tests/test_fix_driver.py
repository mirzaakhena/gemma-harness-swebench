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
