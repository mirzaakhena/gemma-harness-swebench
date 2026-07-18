"""Test logika inti UI log viewer (ui/server.py) — terpisah dari HTTP layer."""
import json

from harness.emit import Emitter
from ui.server import (
    list_campaigns,
    list_runs,
    render_event_line,
    tail_lines,
    validate_name,
)


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
