"""Test panel infografik ringkasan per tahapan (permintaan Mirza 2026-07-20).

Definisi status per case per stage (lihat ui/server.py case_status):
status case = hasil run TERBARU (nomor rerun terbesar) case itu.
PASS r-dev  = verdict pass + pass_l1 true (flip terkonfirmasi).
PASS l-dev  = L1 pass DAN gold_eval qualified true (konsisten
merge_gold_verdict). Selain itu FAIL; artefak tak terbaca -> "?" (fail-soft).
"""
import json

from ui.server import (
    case_status,
    events_fail_detail,
    latest_runs_by_case,
    page_index,
    render_stage_summary,
    stage_summary,
)


def _runs(*ids):
    return [{"run_id": i, "verdict": None, "wall": None} for i in ids]


def _write_verdict(run_dir, phases, wall=None, pass_l1=None):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "verdict.json").write_text(json.dumps({
        "phases": {k: {"verdict": v} for k, v in phases.items()},
        "wall": wall, "pass_l1": pass_l1,
        "finished": "2026-07-20T00:00:01+07:00"}), encoding="utf-8")


def _write_event(run_dir, event, detail):
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event": event, "detail": detail}) + "\n")


def _write_gold(run_dir, obj):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "gold_eval.json").write_text(json.dumps(obj), encoding="utf-8")


# --- latest_runs_by_case -----------------------------------------------------

def test_latest_runs_by_case_picks_biggest_rerun_numeric():
    runs = _runs("c--case-a--r2", "c--case-a--r10", "c--case-a--r9",
                 "c--case-b--r1")
    latest = latest_runs_by_case(runs)
    assert latest == {"case-a": "c--case-a--r10", "case-b": "c--case-b--r1"}


def test_latest_runs_by_case_tolerates_stray_dir():
    latest = latest_runs_by_case(_runs("stray-dir"))
    assert latest == {"stray-dir": "stray-dir"}


# --- case_status: r-dev ------------------------------------------------------

def test_case_status_rdev_pass_needs_pass_l1_true(tmp_path):
    _write_verdict(tmp_path, {"reproduce": "pass"}, pass_l1=True)
    st = case_status("r-dev", tmp_path)
    assert st["status"] == "PASS"


def test_case_status_rdev_pass_without_pass_l1_is_fail(tmp_path):
    # verdict pass tapi flip tak terkonfirmasi (pass_l1 null) -> bukan PASS
    _write_verdict(tmp_path, {"reproduce": "pass"}, pass_l1=None)
    st = case_status("r-dev", tmp_path)
    assert st["status"] == "FAIL"
    assert "flip" in st["category"]


def test_case_status_rdev_wrong_logic_quotes_failures(tmp_path):
    _write_verdict(tmp_path, {"reproduce": "wrong-logic"},
                   wall="reproduce", pass_l1=False)
    _write_event(tmp_path, "exit",
                 {"failures": ["flip test failed: predicate not satisfied"]})
    st = case_status("r-dev", tmp_path)
    assert st["status"] == "FAIL" and st["category"] == "wrong-logic"
    assert any("predicate not satisfied" in r for r in st["reasons"])


def test_case_status_rdev_abort_cites_abort_reason(tmp_path):
    _write_verdict(tmp_path, {}, wall="abort")
    _write_event(tmp_path, "abort", {"reason": "driver crash: NameError"})
    st = case_status("r-dev", tmp_path)
    assert st["status"] == "FAIL" and st["category"] == "abort"
    assert any("driver crash" in r for r in st["reasons"])


def test_case_status_no_recorded_detail_keeps_category_only(tmp_path):
    # JUJUR: tanpa detail terekam -> alasan kosong, kategori saja
    _write_verdict(tmp_path, {"reproduce": "syntax-fail"},
                   wall="reproduce", pass_l1=False)
    st = case_status("r-dev", tmp_path)
    assert st["status"] == "FAIL" and st["category"] == "syntax-fail"
    assert st["reasons"] == []


# --- case_status: l-dev ------------------------------------------------------

def test_case_status_ldev_pass_needs_qualified_true(tmp_path):
    _write_verdict(tmp_path, {"localize": "pass"}, pass_l1=True)
    _write_gold(tmp_path, {"qualified": True})
    assert case_status("l-dev", tmp_path)["status"] == "PASS"


def test_case_status_ldev_qualified_false_shows_candidates_vs_gold(tmp_path):
    _write_verdict(tmp_path, {"localize": "pass"}, pass_l1=True)
    _write_gold(tmp_path, {"qualified": False,
                           "candidate_files": ["a/compiler.py", "a/query.py"],
                           "gold_files": ["a/lookups.py"]})
    st = case_status("l-dev", tmp_path)
    assert st["status"] == "FAIL" and st["category"] == "wrong-file"
    joined = " ".join(st["reasons"])
    assert "a/compiler.py" in joined and "a/lookups.py" in joined
    assert "gold" in joined


def test_case_status_ldev_qualified_false_null_candidates_uses_pointed(
        tmp_path):
    # criterion chosen-file-v1: candidate_files null -> pakai pointed_file
    _write_verdict(tmp_path, {"localize": "pass"}, pass_l1=True)
    _write_gold(tmp_path, {"qualified": False, "candidate_files": None,
                           "pointed_file": "x/wrong.py",
                           "gold_files": ["x/right.py"]})
    st = case_status("l-dev", tmp_path)
    joined = " ".join(st["reasons"])
    assert "x/wrong.py" in joined and "x/right.py" in joined


def test_case_status_ldev_pass_without_gold_eval_is_fail_no_eval(tmp_path):
    _write_verdict(tmp_path, {"localize": "pass"}, pass_l1=True)
    st = case_status("l-dev", tmp_path)
    assert st["status"] == "FAIL"
    assert st["category"] == "pass (no-eval)"


def test_case_status_ldev_l1_fail_quotes_gate_failures(tmp_path):
    _write_verdict(tmp_path, {"localize": "fail"}, wall="localize",
                   pass_l1=False)
    _write_event(tmp_path, "exit",
                 {"failures": ["lines 379-460 extend beyond the end of file"]})
    st = case_status("l-dev", tmp_path)
    assert st["status"] == "FAIL" and st["category"] == "fail"
    assert any("379-460" in r for r in st["reasons"])


# --- case_status: fail-soft --------------------------------------------------

def test_case_status_missing_verdict_is_unknown(tmp_path):
    (tmp_path / "empty-run").mkdir()
    st = case_status("r-dev", tmp_path / "empty-run")
    assert st["status"] == "?"


def test_case_status_broken_verdict_is_unknown(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "verdict.json").write_text("BUKAN JSON{{{", encoding="utf-8")
    st = case_status("r-dev", tmp_path)
    assert st["status"] == "?"


def test_case_status_missing_dir_does_not_crash(tmp_path):
    st = case_status("r-dev", tmp_path / "nope")
    assert st["status"] == "?"


# --- events_fail_detail ------------------------------------------------------

def test_events_fail_detail_last_exit_and_abort(tmp_path):
    _write_event(tmp_path, "exit", {"failures": ["old"]})
    _write_event(tmp_path, "abort", {"why": "trace pool is empty"})
    _write_event(tmp_path, "exit", {"failures": ["artefak wajib tidak ada"]})
    fails, abort = events_fail_detail(tmp_path)
    assert fails == ["artefak wajib tidak ada"]
    assert abort == "trace pool is empty"


def test_events_fail_detail_flip_reason_when_no_failures(tmp_path):
    _write_event(tmp_path, "exit",
                 {"flip": {"flip_ok": False, "reason": "patched still FAIL"}})
    fails, _ = events_fail_detail(tmp_path)
    assert any("patched still FAIL" in f for f in fails)


def test_events_fail_detail_missing_file(tmp_path):
    assert events_fail_detail(tmp_path) == ([], None)


# --- stage_summary + render --------------------------------------------------

def _mk_run(root, camp, case, rerun, phases, wall=None, pass_l1=None):
    run = root / camp / f"{camp}--{case}--r{rerun}"
    _write_verdict(run, phases, wall=wall, pass_l1=pass_l1)
    return run


def test_stage_summary_counts_latest_run_per_case(tmp_path):
    camp = tmp_path / "r-dev"
    # case-a: r1 fail, r2 pass -> status ikut r2 (terbaru) = PASS
    _mk_run(tmp_path, "r-dev", "case-a", 1, {"reproduce": "wrong-logic"},
            wall="reproduce", pass_l1=False)
    _mk_run(tmp_path, "r-dev", "case-a", 2, {"reproduce": "pass"},
            pass_l1=True)
    _mk_run(tmp_path, "r-dev", "case-b", 1, {"reproduce": "syntax-fail"},
            wall="reproduce", pass_l1=False)
    runs = _runs("r-dev--case-a--r1", "r-dev--case-a--r2", "r-dev--case-b--r1")
    s = stage_summary(camp, "r-dev", runs)
    assert (s["total"], s["pass"], s["fail"], s["unknown"]) == (2, 1, 1, 0)
    assert [i["case"] for i in s["items"] if i["status"] == "FAIL"] == [
        "case-b"]


def test_stage_summary_unknown_counted_separately(tmp_path):
    camp = tmp_path / "r-dev"
    (camp / "r-dev--case-x--r1").mkdir(parents=True)  # dir tanpa verdict
    s = stage_summary(camp, "r-dev", _runs("r-dev--case-x--r1"))
    assert (s["total"], s["pass"], s["fail"], s["unknown"]) == (1, 0, 0, 1)


def test_render_stage_summary_text_bar_and_details():
    s = {"total": 4, "pass": 3, "fail": 1, "unknown": 0,
         "items": [
             {"case": "case-a", "rerun": "r2", "status": "PASS",
              "category": "pass", "reasons": []},
             {"case": "case-b", "rerun": "r1", "status": "FAIL",
              "category": "wrong-logic",
              "reasons": ["flip test failed: predicate"]},
         ]}
    out = render_stage_summary(s)
    assert "4 cases" in out
    assert "PASS 3 (75%)" in out and "FAIL 1 (25%)" in out
    assert "class='sbar'" in out and "width:75%" in out  # bar bertumpuk CSS
    assert "<details>" in out and "case-b" in out
    assert "wrong-logic" in out and "predicate" in out
    assert "case-a" not in out.split("<details>")[1]  # PASS tak ikut rincian


def test_render_stage_summary_empty_returns_empty():
    assert render_stage_summary(
        {"total": 0, "pass": 0, "fail": 0, "unknown": 0, "items": []}) == ""


def test_render_stage_summary_escapes_html_in_reasons():
    s = {"total": 1, "pass": 0, "fail": 1, "unknown": 0,
         "items": [{"case": "c", "rerun": "r1", "status": "FAIL",
                    "category": "fail",
                    "reasons": ["<script>alert(1)</script>"]}]}
    out = render_stage_summary(s)
    assert "<script>" not in out and "&lt;script&gt;" in out


# --- integrasi page_index ----------------------------------------------------

def test_page_index_shows_summary_panel(tmp_path):
    _mk_run(tmp_path, "r-dev", "case-a", 1, {"reproduce": "pass"},
            pass_l1=True)
    run_b = _mk_run(tmp_path, "r-dev", "case-b", 1,
                    {"reproduce": "wrong-logic"}, wall="reproduce",
                    pass_l1=False)
    _write_event(run_b, "exit", {"failures": ["flip gagal total"]})
    out = page_index(tmp_path, tab="r-dev")
    assert "2 cases" in out
    assert "PASS 1 (50%)" in out and "FAIL 1 (50%)" in out
    assert "flip gagal total" in out


def test_page_index_summary_covers_all_pages_not_just_page_one(tmp_path):
    # 20 case pass -> tabel terpotong 15/hal, panel tetap hitung 20
    for i in range(20):
        _mk_run(tmp_path, "r-dev", f"case-{i:02d}", 1,
                {"reproduce": "pass"}, pass_l1=True)
    out = page_index(tmp_path, tab="r-dev", page=1)
    assert "20 cases" in out and "PASS 20 (100%)" in out


def test_page_index_no_runs_no_panel(tmp_path):
    (tmp_path / "r-dev").mkdir()
    out = page_index(tmp_path, tab="r-dev")
    assert "cases" not in out  # tanpa run: tanpa panel, tanpa crash
