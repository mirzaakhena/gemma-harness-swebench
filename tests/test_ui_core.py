"""Test logika inti UI log viewer (ui/server.py) — terpisah dari HTTP layer."""
import json

from harness.emit import Emitter
from ui.server import (
    fmt_duration,
    list_campaigns,
    list_runs,
    render_event_line,
    run_duration_seconds,
    tail_lines,
    validate_name,
)


# --- tabs/sort/paging/ikon (permintaan Mirza 2026-07-19 dinihari) -----------

def test_run_sort_key_orders_by_rerun_number():
    from ui.server import run_sort_key
    ids = ["c--x--r2", "c--x--r10", "c--x--r1"]
    ordered = sorted(ids, key=run_sort_key, reverse=True)
    assert ordered == ["c--x--r10", "c--x--r2", "c--x--r1"]


def test_paginate_slices_and_clamps():
    from ui.server import paginate
    items = list(range(35))
    page1, total = paginate(items, 1, per_page=15)
    assert page1 == list(range(15)) and total == 3
    page9, _ = paginate(items, 9, per_page=15)   # clamp ke halaman terakhir
    assert page9 == list(range(30, 35))
    empty, total = paginate([], 1, per_page=15)
    assert empty == [] and total == 1


def test_verdict_icon_mapping():
    from ui.server import verdict_icon
    assert verdict_icon("pass").startswith("✅")
    assert verdict_icon("flip").startswith("✅")
    assert verdict_icon("wrong-logic").startswith("❌")
    assert verdict_icon("syntax-fail").startswith("❌")
    assert verdict_icon("abort") == ""   # keputusan Mirza: abort polos
    assert verdict_icon(None) == ""


# --- kolom ikon terpisah & verdict tanpa prefix (masukan Mirza) -------------

def test_index_row_verdict_single_phase_drops_prefix():
    from ui.server import index_row_verdict
    text, icon = index_row_verdict({"reproduce": "pass"}, None)
    assert text == "pass" and icon.startswith("✅")


def test_index_row_verdict_fail_class():
    from ui.server import index_row_verdict
    text, icon = index_row_verdict({"reproduce": "wrong-logic"}, "reproduce")
    assert text == "wrong-logic" and icon.startswith("❌")


def test_index_row_verdict_abort_without_phases():
    from ui.server import index_row_verdict
    text, icon = index_row_verdict({}, "abort")
    assert text == "abort" and icon == ""


def test_index_row_verdict_multi_phase_keeps_labels():
    from ui.server import index_row_verdict
    text, icon = index_row_verdict(
        {"reproduce": "pass", "localize": "pass"}, None)
    assert "reproduce=pass" in text and "localize=pass" in text
    assert icon.startswith("✅")


# --- turn count & urutan tab (permintaan Mirza 2026-07-19) ------------------

def test_run_turns_from_console(tmp_path):
    from ui.server import run_turns
    (tmp_path / "console.log").write_text(
        "[driver] start\n[gemma t1] hi\n[exec] $ ls\n[gemma t12] more\n",
        encoding="utf-8")
    assert run_turns(tmp_path) == 12


def test_run_turns_none_without_console(tmp_path):
    from ui.server import run_turns
    assert run_turns(tmp_path) is None


def test_campaign_label_maps_known_names():
    from ui.server import campaign_label
    assert campaign_label("r-dev") == "REPRODUCE"
    assert campaign_label("l-dev") == "LOCALIZE"
    assert campaign_label("x-camp") == "x-camp"


def test_order_campaigns_puts_rdev_first():
    from ui.server import order_campaigns
    assert order_campaigns(["l-dev", "r-dev"]) == ["r-dev", "l-dev"]
    assert order_campaigns(["a", "b"]) == ["a", "b"]


# --- durasi run (permintaan Mirza 2026-07-19: tampil di dashboard) ----------

def test_run_duration_seconds_uses_verdict_finished(tmp_path):
    (tmp_path / "events.jsonl").write_text(
        json.dumps({"ts": "2026-07-19T00:00:00+07:00"}) + "\n",
        encoding="utf-8")
    (tmp_path / "verdict.json").write_text(
        json.dumps({"finished": "2026-07-19T00:05:30+07:00"}),
        encoding="utf-8")
    assert run_duration_seconds(tmp_path) == 330.0


def test_run_duration_seconds_live_run_uses_console_mtime(tmp_path):
    (tmp_path / "events.jsonl").write_text(
        json.dumps({"ts": "2026-07-19T00:00:00+07:00"}) + "\n",
        encoding="utf-8")
    (tmp_path / "console.log").write_text("x\n", encoding="utf-8")
    dur = run_duration_seconds(tmp_path)
    assert dur is not None and dur >= 0


def test_run_duration_seconds_none_without_events(tmp_path):
    assert run_duration_seconds(tmp_path) is None


def test_fmt_duration_labels():
    assert fmt_duration(None) == "-"
    assert fmt_duration(45) == "45s"
    assert fmt_duration(330) == "5.5m"


# --- validate_name -----------------------------------------------------------

def test_validate_name_accepts_normal_names():
    assert validate_name("r-dev")
    assert validate_name("r-dev--django__django-11910--r1")
    assert validate_name("Camp_1.x")


def test_validate_name_rejects_traversal_and_junk():
    assert not validate_name("")
    assert not validate_name("..")
    assert not validate_name("a..b")
    assert not validate_name("a/b")
    assert not validate_name("a\\b")
    assert not validate_name("a b")
    assert not validate_name("a\x00b")


# --- tail_lines --------------------------------------------------------------

def test_tail_lines_returns_last_n(tmp_path):
    p = tmp_path / "f.log"
    p.write_text("".join(f"line{i}\n" for i in range(10)), encoding="utf-8")
    assert tail_lines(p, 3) == ["line7", "line8", "line9"]


def test_tail_lines_n_larger_than_file(tmp_path):
    p = tmp_path / "f.log"
    p.write_text("a\nb\n", encoding="utf-8")
    assert tail_lines(p, 200) == ["a", "b"]


def test_tail_lines_missing_file_returns_empty(tmp_path):
    assert tail_lines(tmp_path / "nope.log", 5) == []


# --- list_campaigns ----------------------------------------------------------

def test_list_campaigns_lists_subdirs_only(tmp_path):
    (tmp_path / "camp-b").mkdir()
    (tmp_path / "camp-a").mkdir()
    (tmp_path / "stray.txt").write_text("x", encoding="utf-8")
    assert list_campaigns(tmp_path) == ["camp-a", "camp-b"]


def test_list_campaigns_missing_root_returns_empty(tmp_path):
    assert list_campaigns(tmp_path / "nope") == []


# --- list_runs ---------------------------------------------------------------

def test_list_runs_from_runs_jsonl_via_emitter(tmp_path):
    em = Emitter(tmp_path, "c1", "django__django-11910", 1)
    em.run_start()
    em.run_end(verdict={"reproduce": "pass"}, wall=None)
    runs = list_runs(tmp_path / "c1")
    assert len(runs) == 1
    r = runs[0]
    assert r["run_id"] == "c1--django__django-11910--r1"
    assert r["verdict"] == {"reproduce": "pass"}


def test_list_runs_fallback_dir_listing(tmp_path):
    camp = tmp_path / "c2"
    (camp / "c2--case-x--r1").mkdir(parents=True)
    runs = list_runs(camp)
    assert [r["run_id"] for r in runs] == ["c2--case-x--r1"]
    assert runs[0]["verdict"] is None


def test_list_runs_tolerates_broken_jsonl(tmp_path):
    camp = tmp_path / "c3"
    camp.mkdir()
    (camp / "runs.jsonl").write_text(
        '{"run_id":"c3--ok--r1","event":"start"}\n'
        "INI BUKAN JSON{{{\n",
        encoding="utf-8",
    )
    runs = list_runs(camp)
    assert [r["run_id"] for r in runs] == ["c3--ok--r1"]


def test_list_runs_missing_dir_returns_empty(tmp_path):
    assert list_runs(tmp_path / "nope") == []


# --- render_event_line -------------------------------------------------------

def test_render_event_line_full_event():
    ev = {
        "ts": "2026-07-18T14:03:22+07:00",
        "phase": "reproduce",
        "event": "exit",
        "verdict": "pass",
        "attempt": 2,
        "detail": {"sub_stage": "investigate"},
    }
    line = render_event_line(ev)
    assert "2026-07-18T14:03:22+07:00" in line
    assert "reproduce" in line
    assert "exit" in line
    assert "pass" in line
    assert "a2" in line
    assert "investigate" in line


def test_render_event_line_minimal_does_not_crash():
    line = render_event_line({})
    assert isinstance(line, str)


def test_render_event_line_truncates_long_detail():
    ev = {"ts": "t", "phase": "fix", "event": "retry",
          "detail": {"blob": "x" * 500}}
    line = render_event_line(ev)
    assert len(line) < 300


# --- kolom case & run terpisah (permintaan Mirza 2026-07-19) ----------------

def test_split_run_id_basic():
    from ui.server import split_run_id
    assert split_run_id("r-dev--django__django-13220--r6") == (
        "django__django-13220", "r6")


def test_split_run_id_case_with_dashes_and_underscores():
    from ui.server import split_run_id
    assert split_run_id("c1--sympy__sympy-13971--r12") == (
        "sympy__sympy-13971", "r12")


def test_split_run_id_fallback_nonconforming():
    from ui.server import split_run_id
    # direktori nyasar tanpa format <campaign>--<case>--rN: tampil apa adanya
    assert split_run_id("stray-dir") == ("stray-dir", "")


def test_page_index_splits_case_and_run_columns(tmp_path):
    from ui.server import page_index
    run = tmp_path / "r-dev" / "r-dev--django__django-13220--r6"
    run.mkdir(parents=True)
    out = page_index(tmp_path)
    assert "<th>case</th><th>run</th>" in out
    assert "<td>django__django-13220</td>" in out          # case polos
    assert ">r6</a>" in out                                # rN ber-link
    assert "r-dev--django__django-13220--r6</a>" not in out  # run_id penuh hilang


# --- sort by started datetime (permintaan Mirza 2026-07-19) ----------------

def test_sort_runs_desc_by_started_datetime(tmp_path):
    from ui.server import sort_runs_desc
    camp = tmp_path / "r-dev"
    old = camp / "r-dev--django__django-11422--r44"
    new = camp / "r-dev--django__django-11999--r1"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    (old / "events.jsonl").write_text(
        '{"ts": "2026-07-19T02:00:00+07:00", "event": "enter"}\n',
        encoding="utf-8")
    (new / "events.jsonl").write_text(
        '{"ts": "2026-07-19T04:50:00+07:00", "event": "enter"}\n',
        encoding="utf-8")
    runs = [{"run_id": old.name, "verdict": None, "wall": None},
            {"run_id": new.name, "verdict": None, "wall": None}]
    ordered = sort_runs_desc(runs, camp)
    assert ordered[0]["run_id"] == new.name  # started terbaru duluan


def test_sort_runs_desc_missing_events_falls_back_to_rerun(tmp_path):
    from ui.server import sort_runs_desc
    camp = tmp_path / "r-dev"
    camp.mkdir(parents=True)
    runs = [{"run_id": "x--c--r2", "verdict": None, "wall": None},
            {"run_id": "x--c--r7", "verdict": None, "wall": None}]
    ordered = sort_runs_desc(runs, camp)
    assert ordered[0]["run_id"] == "x--c--r7"
