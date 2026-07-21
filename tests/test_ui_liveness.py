"""Test label keaktifan run tanpa verdict.json (bugfix observability
2026-07-21): run yang DIBUNUH dari luar tak pernah menulis verdict.json,
dulu tampil "(live)" selamanya. Sekarang dibedakan lewat mtime terbaru
console.log/events.jsonl: baru -> "(live)", beku -> "(stale?)".

Definisi: live bila (now - mtime_terbaru) <= STALE_THRESHOLD_SECONDS (300s);
kedua file hilang -> stale (tak ada bukti keaktifan). Run DENGAN verdict.json
(termasuk verdict "abort" yang SAH) tak masuk jalur ini sama sekali.
"""
import json
import os
import time
from datetime import datetime

from ui.server import (
    STALE_THRESHOLD_SECONDS,
    page_index,
    page_run,
    run_liveness,
)


# --- helper murni run_liveness (now eksplisit -> tak flaky) ------------------

def test_run_liveness_fresh_mtime_is_live(tmp_path):
    (tmp_path / "console.log").write_text("x\n", encoding="utf-8")
    os.utime(tmp_path / "console.log", (1000.0, 1000.0))
    assert run_liveness(tmp_path, now=1000.0) == "live"
    # tepat di ambang -> masih live
    assert run_liveness(tmp_path, now=1000.0 + STALE_THRESHOLD_SECONDS) == "live"


def test_run_liveness_old_mtime_is_stale(tmp_path):
    (tmp_path / "console.log").write_text("x\n", encoding="utf-8")
    os.utime(tmp_path / "console.log", (1000.0, 1000.0))
    # 600s > 300s ambang -> beku
    assert run_liveness(tmp_path, now=1000.0 + 600) == "stale"


def test_run_liveness_uses_latest_of_two_files(tmp_path):
    (tmp_path / "console.log").write_text("x\n", encoding="utf-8")
    (tmp_path / "events.jsonl").write_text("{}\n", encoding="utf-8")
    os.utime(tmp_path / "console.log", (1000.0, 1000.0))     # lama
    os.utime(tmp_path / "events.jsonl", (1900.0, 1900.0))    # baru
    # ambil mtime terbaru (events.jsonl) -> live pada now dekat 1900
    assert run_liveness(tmp_path, now=1950.0) == "live"


def test_run_liveness_missing_both_files_is_stale(tmp_path):
    assert run_liveness(tmp_path, now=1000.0) == "stale"


def test_run_liveness_missing_dir_is_stale(tmp_path):
    assert run_liveness(tmp_path / "nope", now=1000.0) == "stale"


def test_run_liveness_accepts_datetime_now(tmp_path):
    dt = datetime(2026, 7, 21, 12, 0, 0)
    (tmp_path / "events.jsonl").write_text("{}\n", encoding="utf-8")
    os.utime(tmp_path / "events.jsonl", (dt.timestamp(), dt.timestamp()))
    assert run_liveness(tmp_path, now=dt) == "live"


# --- render label di page_index (mtime nyata via os.utime, threshold longgar)

def _mk_run_dir(tmp_path, campaign, case, rerun="r1"):
    run = tmp_path / campaign / f"{campaign}--{case}--{rerun}"
    run.mkdir(parents=True)
    return run


def test_page_index_fresh_run_labeled_live(tmp_path):
    run = _mk_run_dir(tmp_path, "r-dev", "django__django-11019")
    (run / "console.log").write_text("[gemma t1] hi\n", encoding="utf-8")
    # mtime = sekarang -> live (page_index pakai time.time() internal)
    os.utime(run / "console.log", None)
    out = page_index(tmp_path, tab="r-dev")
    assert "(live)" in out
    assert "(stale?)" not in out


def test_page_index_frozen_run_labeled_stale(tmp_path):
    run = _mk_run_dir(tmp_path, "r-dev", "django__django-15819")
    (run / "console.log").write_text("[gemma t3] hi\n", encoding="utf-8")
    old = time.time() - 600  # 10 menit lalu, jauh di atas ambang 300s
    os.utime(run / "console.log", (old, old))
    out = page_index(tmp_path, tab="r-dev")
    assert "(stale?)" in out
    assert "(live)" not in out


def test_page_index_abort_run_keeps_verdict_not_stale(tmp_path):
    # verdict "abort" adalah vonis SAH (punya verdict.json) -> TIDAK masuk
    # jalur no-verdict; label live/stale tak boleh muncul untuk baris ini.
    run = _mk_run_dir(tmp_path, "r-dev", "django__django-11620", rerun="r2")
    (run / "verdict.json").write_text(json.dumps({
        "phases": {}, "wall": "abort",
        "finished": "2026-07-21T00:05:00+07:00"}), encoding="utf-8")
    (run / "events.jsonl").write_text(
        json.dumps({"ts": "2026-07-21T00:00:00+07:00", "event": "start"})
        + "\n", encoding="utf-8")
    out = page_index(tmp_path, tab="r-dev")
    assert "abort" in out
    assert "(live)" not in out and "(stale?)" not in out


# --- smoke page_index: stale & live berdampingan -----------------------------

def test_page_index_live_and_stale_coexist(tmp_path):
    live_run = _mk_run_dir(tmp_path, "r-dev", "django__django-100")
    (live_run / "console.log").write_text("x\n", encoding="utf-8")
    os.utime(live_run / "console.log", None)  # sekarang -> live
    dead_run = _mk_run_dir(tmp_path, "r-dev", "django__django-200")
    (dead_run / "console.log").write_text("x\n", encoding="utf-8")
    old = time.time() - 900
    os.utime(dead_run / "console.log", (old, old))
    out = page_index(tmp_path, tab="r-dev")
    assert "(live)" in out and "(stale?)" in out


# --- page_run juga menempel label yang sama ----------------------------------

def test_page_run_frozen_run_labeled_stale(tmp_path):
    run = _mk_run_dir(tmp_path, "r-dev", "django__django-15819")
    (run / "events.jsonl").write_text(
        json.dumps({"ts": "2026-07-21T00:00:00+07:00", "event": "start"})
        + "\n", encoding="utf-8")
    old = time.time() - 600
    os.utime(run / "events.jsonl", (old, old))
    out = page_run(tmp_path, "r-dev", "r-dev--django__django-15819--r1", 50)
    assert "(stale?)" in out
    assert "(live)" not in out
