"""Test status 2-lapisan dashboard (spec §6) — kampanye f-*."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))
import server  # noqa: E402


def _mk_run(tmp_path, verdict="flip", pass_l1=True, swebench=None,
            rerun=1):
    run_dir = tmp_path / "f-dev" / f"f-dev--django__django-1--r{rerun}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "verdict.json").write_text(json.dumps(
        {"phases": {"fix": {"verdict": verdict}}, "wall": None,
         "pass_l1": pass_l1}), encoding="utf-8")
    if swebench is not None:
        (run_dir / "swebench_eval.json").write_text(
            json.dumps(swebench), encoding="utf-8")
    return run_dir


def test_pass_when_both_layers_pass(tmp_path):
    rd = _mk_run(tmp_path, swebench={"resolved": True})
    st = server.case_status("f-dev", rd)
    assert st["status"] == "PASS"


def test_wait_when_no_swebench_eval(tmp_path):
    rd = _mk_run(tmp_path, swebench=None)
    st = server.case_status("f-dev", rd)
    assert st["status"] == "WAIT"
    assert "VERIFY" in st["category"]


def test_fail_verify_lists_regressions(tmp_path):
    rd = _mk_run(tmp_path, swebench={
        "resolved": False, "patch_successfully_applied": True,
        "f2p_failed": [], "p2p_failed": ["test_x (a.B)"]})
    st = server.case_status("f-dev", rd)
    assert st["status"] == "FAIL"
    assert st["category"] == "verify-fail"
    assert any("test_x (a.B)" in r for r in st["reasons"])


def test_anomaly_product_fail_but_resolved(tmp_path):
    rd = _mk_run(tmp_path, verdict="no-flip", pass_l1=False,
                 swebench={"resolved": True})
    st = server.case_status("f-dev", rd)
    assert st["status"] == "ANOMALY"


def test_product_fail_plain_stays_fail(tmp_path):
    rd = _mk_run(tmp_path, verdict="no-flip", pass_l1=False, swebench=None)
    st = server.case_status("f-dev", rd)
    assert st["status"] == "FAIL"


def test_stage_summary_counts_new_states(tmp_path):
    _mk_run(tmp_path, rerun=1, swebench={"resolved": True})
    runs = [{"run_id": "f-dev--django__django-1--r1"}]
    s = server.stage_summary(tmp_path / "f-dev", "f-dev", runs)
    assert s["pass"] == 1 and s["wait"] == 0 and s["anomaly"] == 0
    html_out = server.render_stage_summary(s)
    assert "PASS 1" in html_out
