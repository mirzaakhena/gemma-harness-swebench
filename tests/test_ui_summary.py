"""Test panel infografik ringkasan per tahapan (permintaan Mirza 2026-07-20).

Definisi status per case per stage = "pernah qualified" (keputusan Mirza
2026-07-20): case PASS bila ADA >=1 run-nya yang qualified di kampanye itu.
Qualified per run (lihat ui/server.py case_status):
  r-dev = verdict pass + pass_l1 true (flip terkonfirmasi).
  l-dev = L1 pass DAN gold_eval qualified true (konsisten merge_gold_verdict).
Case FAIL hanya bila TAK PERNAH ada run qualified; kategori+alasan diambil
dari run TERBARU case itu. Artefak tak terbaca -> "?" (fail-soft).
"""
import json

from ui.server import (
    case_status,
    events_fail_detail,
    latest_runs_by_case,
    page_index,
    render_stage_summary,
    run_started_str,
    stage_summary,
)


def _runs(*ids):
    return [{"run_id": i, "verdict": None, "wall": None} for i in ids]


def _write_verdict(run_dir, phases, wall=None, pass_l1=None, started=None):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "verdict.json").write_text(json.dumps({
        "phases": {k: {"verdict": v} for k, v in phases.items()},
        "wall": wall, "pass_l1": pass_l1, "started": started,
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


# --- run_started_str (permintaan Mirza 2026-07-20: tanggal pengujian) --------

def test_run_started_str_formats_compact_without_offset(tmp_path):
    _write_verdict(tmp_path, {"reproduce": "pass"}, pass_l1=True,
                   started="2026-07-19T21:42:54+07:00")
    assert run_started_str(tmp_path) == "2026-07-19 21:42"


def test_run_started_str_null_started_without_events_is_question(tmp_path):
    # run legacy: started null, tanpa events.jsonl -> "?" (fail-soft)
    _write_verdict(tmp_path, {"reproduce": "pass"}, pass_l1=True)
    assert run_started_str(tmp_path) == "?"


def test_run_started_str_broken_iso_is_question(tmp_path):
    _write_verdict(tmp_path, {"reproduce": "pass"}, pass_l1=True,
                   started="kemarin sore")
    assert run_started_str(tmp_path) == "?"


def test_run_started_str_live_run_falls_back_to_first_event_ts(tmp_path):
    # run hidup: verdict.json belum ada -> pakai ts event pertama
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "events.jsonl").write_text(
        json.dumps({"ts": "2026-07-20T08:05:00+07:00", "event": "start"})
        + "\n", encoding="utf-8")
    assert run_started_str(tmp_path) == "2026-07-20 08:05"


def test_run_started_str_missing_dir_is_question(tmp_path):
    assert run_started_str(tmp_path / "nope") == "?"


# --- stage_summary + render --------------------------------------------------

def _mk_run(root, camp, case, rerun, phases, wall=None, pass_l1=None,
            started=None):
    run = root / camp / f"{camp}--{case}--r{rerun}"
    _write_verdict(run, phases, wall=wall, pass_l1=pass_l1, started=started)
    return run


def test_stage_summary_counts_one_status_per_case(tmp_path):
    camp = tmp_path / "r-dev"
    # case-a: r1 fail, r2 qualified -> pernah qualified = PASS
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


def test_stage_summary_ever_qualified_early_pass_late_fail_is_pass(tmp_path):
    # KUNCI keputusan Mirza 2026-07-20: r1 qualified + r3 gagal -> tetap PASS
    camp = tmp_path / "r-dev"
    _mk_run(tmp_path, "r-dev", "case-a", 1, {"reproduce": "pass"},
            pass_l1=True)
    _mk_run(tmp_path, "r-dev", "case-a", 2, {"reproduce": "wrong-logic"},
            wall="reproduce", pass_l1=False)
    _mk_run(tmp_path, "r-dev", "case-a", 3, {"reproduce": "syntax-fail"},
            wall="reproduce", pass_l1=False)
    s = stage_summary(camp, "r-dev", _runs(
        "r-dev--case-a--r1", "r-dev--case-a--r2", "r-dev--case-a--r3"))
    assert (s["total"], s["pass"], s["fail"], s["unknown"]) == (1, 1, 0, 0)
    item = s["items"][0]
    assert item["status"] == "PASS"
    assert item["rerun"] == "r1"  # run qualified yang dirujuk


def test_stage_summary_never_qualified_reason_from_latest_run(tmp_path):
    # 0 run qualified -> FAIL; kategori+alasan dari run TERBARU (r2)
    camp = tmp_path / "r-dev"
    run1 = _mk_run(tmp_path, "r-dev", "case-a", 1,
                   {"reproduce": "syntax-fail"}, wall="reproduce",
                   pass_l1=False)
    _write_event(run1, "exit", {"failures": ["alasan lama r1"]})
    run2 = _mk_run(tmp_path, "r-dev", "case-a", 2,
                   {"reproduce": "wrong-logic"}, wall="reproduce",
                   pass_l1=False)
    _write_event(run2, "exit", {"failures": ["alasan terbaru r2"]})
    s = stage_summary(camp, "r-dev", _runs(
        "r-dev--case-a--r1", "r-dev--case-a--r2"))
    item = s["items"][0]
    assert item["status"] == "FAIL"
    assert item["rerun"] == "r2" and item["category"] == "wrong-logic"
    assert any("alasan terbaru r2" in r for r in item["reasons"])
    assert not any("alasan lama r1" in r for r in item["reasons"])


def test_stage_summary_unknown_counted_separately(tmp_path):
    camp = tmp_path / "r-dev"
    (camp / "r-dev--case-x--r1").mkdir(parents=True)  # dir tanpa verdict
    s = stage_summary(camp, "r-dev", _runs("r-dev--case-x--r1"))
    assert (s["total"], s["pass"], s["fail"], s["unknown"]) == (1, 0, 0, 1)


def test_stage_summary_item_started_refers_to_chosen_run(tmp_path):
    # PASS merujuk run qualified (r1) -> tanggal ikut run ITU, bukan terbaru
    camp = tmp_path / "r-dev"
    _mk_run(tmp_path, "r-dev", "case-a", 1, {"reproduce": "pass"},
            pass_l1=True, started="2026-07-18T10:00:00+07:00")
    _mk_run(tmp_path, "r-dev", "case-a", 2, {"reproduce": "wrong-logic"},
            wall="reproduce", pass_l1=False,
            started="2026-07-19T11:30:00+07:00")
    s = stage_summary(camp, "r-dev",
                      _runs("r-dev--case-a--r1", "r-dev--case-a--r2"))
    item = s["items"][0]
    assert item["status"] == "PASS"
    assert item["started"] == "2026-07-18 10:00"


def test_stage_summary_item_started_fail_uses_latest_run_date(tmp_path):
    camp = tmp_path / "r-dev"
    _mk_run(tmp_path, "r-dev", "case-a", 1, {"reproduce": "syntax-fail"},
            wall="reproduce", pass_l1=False,
            started="2026-07-18T10:00:00+07:00")
    _mk_run(tmp_path, "r-dev", "case-a", 2, {"reproduce": "wrong-logic"},
            wall="reproduce", pass_l1=False,
            started="2026-07-19T11:30:00+07:00")
    s = stage_summary(camp, "r-dev",
                      _runs("r-dev--case-a--r1", "r-dev--case-a--r2"))
    item = s["items"][0]
    assert item["status"] == "FAIL"
    assert item["started"] == "2026-07-19 11:30"


def test_stage_summary_item_started_missing_is_question(tmp_path):
    camp = tmp_path / "r-dev"
    _mk_run(tmp_path, "r-dev", "case-a", 1, {"reproduce": "syntax-fail"},
            wall="reproduce", pass_l1=False)  # started null, tanpa events
    s = stage_summary(camp, "r-dev", _runs("r-dev--case-a--r1"))
    assert s["items"][0]["started"] == "?"


def test_render_stage_summary_text_bar_and_info():
    s = {"total": 4, "pass": 3, "fail": 1, "unknown": 0,
         "items": [
             {"case": "case-a", "rerun": "r2", "status": "PASS",
              "category": "pass", "reasons": []},
             {"case": "case-b", "rerun": "r1", "status": "FAIL",
              "category": "wrong-logic",
              "reasons": ["flip test failed: predicate"]},
         ]}
    out = render_stage_summary(s)
    assert "<div class='num'>4</div>" in out and "cases" in out
    assert "✅ 3" in out and "PASS 75%" in out
    assert "❌ 1" in out and "FAIL 25%" in out
    assert "class='sbar'" in out and "width:75%" in out  # bar bertumpuk CSS
    # rincian FAIL/ANOMALY tak lagi di panel (pindah ke modal ikon tabel utama)
    assert "rincian FAIL" not in out
    # label [info] + modal legenda dibuang (permintaan Mirza 2026-07-22)
    assert "[info]" not in out


def test_render_stage_summary_no_legend_definition_in_panel():
    # legenda "pernah qualified" dibuang by design bersama modal
    # "[info]"/legendBody (Mirza 2026-07-22) — definisi status tak lagi
    # ditampilkan di panel maupun disalin ke modal manapun
    s = {"total": 2, "pass": 1, "fail": 1, "unknown": 0,
         "items": [
             {"case": "case-a", "rerun": "r1", "status": "PASS",
              "category": "pass", "reasons": []},
             {"case": "case-b", "rerun": "r2", "status": "FAIL",
              "category": "fail", "reasons": []},
         ]}
    out = render_stage_summary(s)
    assert "pernah qualified" not in out
    assert "legendBody" not in out


def test_render_stage_summary_no_fail_details_table_in_panel():
    # rincian FAIL pindah ke modal ikon tabel utama; panel hanya head+bar+info
    s = {"total": 1, "pass": 0, "fail": 1, "unknown": 0,
         "items": [{"case": "case-b", "rerun": "r2", "status": "FAIL",
                    "category": "wrong-logic", "reasons": [],
                    "started": "2026-07-19 11:30"}]}
    out = render_stage_summary(s)
    assert "❌ 1" in out and "FAIL 100%" in out
    assert "rincian FAIL" not in out
    assert "<th>kategori</th>" not in out


def test_render_stage_summary_no_pass_list_block():
    # blok "daftar PASS" dihapus (permintaan Mirza 2026-07-21) — diganti
    # radio filter di tabel utama; panel hanya menyisakan head+bar+info
    s = {"total": 2, "pass": 1, "fail": 1, "unknown": 0,
         "items": [
             {"case": "case-a", "rerun": "r1", "status": "PASS",
              "category": "pass", "reasons": [],
              "started": "2026-07-18 10:00"},
             {"case": "case-b", "rerun": "r2", "status": "FAIL",
              "category": "fail", "reasons": [],
              "started": "2026-07-19 11:30"},
         ]}
    out = render_stage_summary(s)
    assert "daftar PASS" not in out
    assert "PASS 50%" in out


def test_render_stage_summary_no_pass_no_pass_list():
    s = {"total": 1, "pass": 0, "fail": 1, "unknown": 0,
         "items": [{"case": "case-b", "rerun": "r1", "status": "FAIL",
                    "category": "fail", "reasons": [],
                    "started": "?"}]}
    out = render_stage_summary(s)
    assert "daftar PASS" not in out


def test_render_stage_summary_empty_returns_empty():
    assert render_stage_summary(
        {"total": 0, "pass": 0, "fail": 0, "unknown": 0, "items": []}) == ""


def test_page_index_escapes_html_in_reason_attribute(tmp_path):
    # alasan pindah ke atribut data-reason tombol ❌ di tabel utama; tetap
    # di-escape (permintaan Mirza: tanpa dependency, aman dari injeksi)
    run_b = _mk_run(tmp_path, "r-dev", "case-b", 1,
                    {"reproduce": "wrong-logic"}, wall="reproduce",
                    pass_l1=False)
    _write_event(run_b, "exit", {"failures": ["<script>alert(1)</script>"]})
    out = page_index(tmp_path, tab="r-dev")
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


# --- integrasi page_index ----------------------------------------------------

def test_page_index_shows_summary_panel(tmp_path):
    _mk_run(tmp_path, "r-dev", "case-a", 1, {"reproduce": "pass"},
            pass_l1=True)
    run_b = _mk_run(tmp_path, "r-dev", "case-b", 1,
                    {"reproduce": "wrong-logic"}, wall="reproduce",
                    pass_l1=False)
    _write_event(run_b, "exit", {"failures": ["flip gagal total"]})
    out = page_index(tmp_path, tab="r-dev")
    assert "<div class='num'>2</div>" in out and "cases" in out
    assert "✅ 1" in out and "PASS 50%" in out
    assert "❌ 1" in out and "FAIL 50%" in out
    assert "flip gagal total" in out


def test_page_index_summary_covers_all_pages_not_just_page_one(tmp_path):
    # 20 case pass -> tabel terpotong 15/hal, panel tetap hitung 20
    for i in range(20):
        _mk_run(tmp_path, "r-dev", f"case-{i:02d}", 1,
                {"reproduce": "pass"}, pass_l1=True)
    out = page_index(tmp_path, tab="r-dev", page=1)
    assert "<div class='num'>20</div>" in out and "cases" in out
    assert "✅ 20" in out and "PASS 100%" in out


def test_page_index_run_table_shows_started_column(tmp_path):
    _mk_run(tmp_path, "r-dev", "case-a", 1, {"reproduce": "pass"},
            pass_l1=True, started="2026-07-19T21:42:54+07:00")
    out = page_index(tmp_path, tab="r-dev")
    assert "<th>mulai</th>" in out
    assert "2026-07-19 21:42" in out


def test_page_index_no_runs_no_panel(tmp_path):
    (tmp_path / "r-dev").mkdir()
    out = page_index(tmp_path, tab="r-dev")
    assert "cases" not in out  # tanpa run: tanpa panel, tanpa crash


# --- perilaku baru: radio filter, kolom mulai dipindah, [info], modal ❌ ------

def test_page_index_mulai_column_moved_after_turns(tmp_path):
    # urutan kolom baru: case|run|(ikon)|verdict|durasi|turns|mulai
    _mk_run(tmp_path, "r-dev", "case-a", 1, {"reproduce": "pass"},
            pass_l1=True, started="2026-07-19T21:42:54+07:00")
    out = page_index(tmp_path, tab="r-dev")
    header = ("<th>case</th><th>run</th><th></th><th>verdict</th>"
              "<th>durasi</th><th>turns</th><th>mulai</th>")
    assert header in out


def test_page_index_has_row_radio_filter(tmp_path):
    _mk_run(tmp_path, "r-dev", "case-a", 1, {"reproduce": "pass"},
            pass_l1=True)
    out = page_index(tmp_path, tab="r-dev")
    # tiga radio All/PASS/FAIL (server-side, dulu client-side JS filterRows)
    # + data-status di baris (dipakai test; permintaan Mirza 2026-07-22)
    assert "value='All'" in out and "value='PASS'" in out \
        and "value='FAIL'" in out
    assert "class='rfilter'" in out  # server-side form
    assert 'data-status="PASS"' in out


def test_page_index_no_info_legend_modal(tmp_path):
    # tombol "[info]" + modal legenda dibuang dari page_index (Mirza
    # 2026-07-22) — dulu tes ini memverifikasi modal ADA, sekarang
    # memverifikasi fitur itu memang sudah tidak ada (by design)
    _mk_run(tmp_path, "r-dev", "case-a", 1, {"reproduce": "pass"},
            pass_l1=True)
    out = page_index(tmp_path, tab="r-dev")
    assert "[info]" not in out and "showInfo" not in out
    assert "legendBody" not in out and "pernah qualified" not in out


def test_page_index_fail_icon_carries_case_reason(tmp_path):
    run_b = _mk_run(tmp_path, "r-dev", "case-b", 1,
                    {"reproduce": "wrong-logic"}, wall="reproduce",
                    pass_l1=False)
    _write_event(run_b, "exit", {"failures": ["flip gagal total"]})
    out = page_index(tmp_path, tab="r-dev")
    # ikon ❌ jadi tombol pembuka modal, membawa alasan case via data-reason
    assert "showReason(this)" in out
    assert "data-reason=" in out and "flip gagal total" in out
