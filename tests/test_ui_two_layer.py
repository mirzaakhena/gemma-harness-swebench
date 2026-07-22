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


def test_tab_label_fix_and_verify_no_fourth_tab():
    assert server.campaign_label("f-dev") == "FIX and VERIFY"
    assert "v-dev" not in server.with_stage_tabs(["r-dev"])


def test_page_run_shows_verify_sections(tmp_path):
    rd = _mk_run(tmp_path, swebench={
        "resolved": True, "patch_successfully_applied": True,
        "f2p_passed": ["test_a (a.B)"], "f2p_failed": [],
        "p2p_passed_count": 7, "p2p_failed": [],
        "log": "files/swebench_test_output.log"})
    (rd / "gold_eval.json").write_text(json.dumps(
        {"touched_files": ["x.py"], "gold_files": ["x.py"],
         "file_match": True, "line_overlap": True}), encoding="utf-8")
    (rd / "files").mkdir(exist_ok=True)
    (rd / "files" / "swebench_test_output.log").write_text(
        "test_a (a.B) ... ok\n", encoding="utf-8")
    html_out = server.page_run(tmp_path, "f-dev",
                               "f-dev--django__django-1--r1", 200)
    assert "VERIFY (SWE-bench)" in html_out
    assert "resolved" in html_out
    assert "gold-match (advisory)" in html_out
    assert "swebench_test_output.log" in html_out


def test_page_run_verify_waiting_note(tmp_path):
    _mk_run(tmp_path, swebench=None)
    html_out = server.page_run(tmp_path, "f-dev",
                               "f-dev--django__django-1--r1", 200)
    assert "menunggu VERIFY" in html_out


# --- Fix A: ikon baris tabel index sinkron dgn status 2-lapisan -------------

def test_page_index_row_icon_reflects_verify_fail(tmp_path):
    """verify-fail (flip + pass_l1 true tapi swebench resolved=false) harus
    tampil ❌ di ikon baris, bukan ✅ dari verdict.json mentah — teks verdict
    tetap 'flip' (keputusan Mirza: teks = vonis L1 produk apa adanya)."""
    _mk_run(tmp_path, verdict="flip", pass_l1=True, swebench={
        "resolved": False, "patch_successfully_applied": True,
        "f2p_failed": [], "p2p_failed": []})
    out = server.page_index(tmp_path, tab="f-dev")
    assert ">flip<" in out
    # ikon ❌ kini elemen clickable (button) pembuka modal alasan, bukan
    # <td>❌</td> polos; baris tetap data-status FAIL, tak ada ✅
    assert "❌" in out and "<button" in out
    assert 'data-status="FAIL"' in out
    # ikon BARIS tabel tak boleh ✅; kartu ringkasan PASS 0 sah memuat ✅
    assert "<td>✅" not in out


def test_page_index_row_icon_wait_shows_hourglass(tmp_path):
    """product-pass tanpa swebench_eval.json (WAIT) -> ikon ⏳, bukan ✅."""
    _mk_run(tmp_path, verdict="flip", pass_l1=True, swebench=None)
    out = server.page_index(tmp_path, tab="f-dev")
    assert "<td>⏳ </td>" in out
    assert "<td>✅ </td>" not in out


def test_page_index_row_icon_unaffected_for_non_f_campaigns(tmp_path):
    """r-dev/l-dev: ikon baris TETAP dari verdict.json mentah (byte-identical
    dgn perilaku lama) — TIDAK boleh di-override oleh case_status, walau
    case_status utk run ini sebenarnya FAIL (pass_l1 false)."""
    run_dir = tmp_path / "r-dev" / "r-dev--case-a--r1"
    run_dir.mkdir(parents=True)
    (run_dir / "verdict.json").write_text(json.dumps(
        {"phases": {"reproduce": {"verdict": "pass"}}, "wall": None,
         "pass_l1": False}), encoding="utf-8")
    assert server.case_status("r-dev", run_dir)["status"] == "FAIL"
    out = server.page_index(tmp_path, tab="r-dev")
    assert "<td>✅ </td>" in out


# --- Fix C: page_run wording produk-FAIL vs product-pass menunggu VERIFY ---

def test_page_run_no_flip_run_does_not_say_product_pass_waiting(tmp_path):
    _mk_run(tmp_path, verdict="no-flip", pass_l1=False, swebench=None)
    html_out = server.page_run(tmp_path, "f-dev",
                               "f-dev--django__django-1--r1", 200)
    assert "product-pass, menunggu VERIFY" not in html_out
    assert "product FAIL" in html_out


# --- Fix D: product_pass dari phases.fix.verdict, bukan vtext render -------

def test_multi_phase_verdict_fix_flip_classified_pass(tmp_path):
    """verdict.json masa depan bisa punya >1 fase (vtext jadi 'fix=flip
    other=...' majemuk) — deteksi product_pass HARUS baca phases.fix.verdict
    langsung, bukan vtext render, supaya tetap PASS bukan ANOMALY."""
    run_dir = tmp_path / "f-dev" / "f-dev--django__django-2--r1"
    run_dir.mkdir(parents=True)
    (run_dir / "verdict.json").write_text(json.dumps({
        "phases": {"fix": {"verdict": "flip"},
                  "other": {"verdict": "pass"}},
        "wall": None, "pass_l1": True}), encoding="utf-8")
    (run_dir / "swebench_eval.json").write_text(
        json.dumps({"resolved": True}), encoding="utf-8")
    st = server.case_status("f-dev", run_dir)
    assert st["status"] == "PASS"
