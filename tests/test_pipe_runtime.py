"""Test pipe_runtime — runtime helper yang dikirim harness ke sandbox.

Keputusan Mirza 2026-07-19 (pasca-r32): bagian "menyalakan aplikasi &
menunggu siap" dipindah dari disiplin prompt ke fisika modul — settle
baseline otomatis di SETIAP ready (start + tiap reload/restart), semua
output child di-echo (kelas trace-tertelan r29/r30 mati). Modul ini
disalin ke /testbed/.pipe/ di container kerja DAN container gate, jadi
repro.py tetap self-contained (import lokal).

Kendala target: Python 3.6 di container testbed (r21) — modul harus
kompatibel; test berjalan di host (Windows) memakai fake child process.
"""
import subprocess
import sys
import time
from pathlib import Path

import pytest

from harness.stages.pipe_runtime import App

FAKE_DIR = None  # diisi fixture


def _write(tmp_path: Path, name: str, body: str) -> str:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8", newline="\n")
    return str(p)


@pytest.fixture()
def fake(tmp_path):
    def make(name, body):
        return [sys.executable, "-u", _write(tmp_path, name, body)]
    return make


READY_ONCE = """\
import time
print("APP READY", flush=True)
print("EVT ALPHA", flush=True)
time.sleep(30)
"""

READY_TWICE = """\
import time
print("APP READY", flush=True)
time.sleep(0.5)
print("APP READY", flush=True)
time.sleep(30)
"""

NEVER_READY = """\
import time
print("warming up", flush=True)
time.sleep(30)
"""

EXIT_EARLY = """\
print("boom", flush=True)
raise SystemExit(1)
"""

READY_RELOAD = """\
import time
print("APP READY", flush=True)
time.sleep(0.3)
print("/x/settings.py changed, reloading.", flush=True)
print("APP READY", flush=True)
time.sleep(30)
"""


def test_start_waits_for_ready_and_settles(fake):
    app = App(fake("a.py", READY_ONCE), ready_token="APP READY",
              interval=0.1, settle=0.3)
    t0 = time.time()
    app.start(timeout=10)
    elapsed = time.time() - t0
    try:
        assert elapsed >= 0.3  # settle terjadi
    finally:
        app.stop()


def test_child_output_is_echoed(fake, capsys):
    app = App(fake("b.py", READY_ONCE), ready_token="APP READY",
              interval=0.1, settle=0.1)
    app.start(timeout=10)
    app.stop()
    out = capsys.readouterr().out
    assert "APP READY" in out


def test_wait_ready_detects_restart(fake):
    app = App(fake("c.py", READY_TWICE), ready_token="APP READY",
              interval=0.1, settle=0.1)
    app.start(timeout=10)
    try:
        assert app.wait_ready(timeout=5) is True
    finally:
        app.stop()


def test_wait_ready_returns_false_without_restart(fake):
    app = App(fake("d.py", READY_ONCE), ready_token="APP READY",
              interval=0.1, settle=0.1)
    app.start(timeout=10)
    try:
        assert app.wait_ready(timeout=0.8) is False
    finally:
        app.stop()


def test_wait_for_finds_scenario_line(fake):
    app = App(fake("e.py", READY_ONCE), ready_token="APP READY",
              interval=0.1, settle=0.1)
    app.start(timeout=10)
    try:
        assert app.wait_for("EVT ALPHA", timeout=5) is True
        assert app.wait_for("EVT OMEGA", timeout=0.5) is False
    finally:
        app.stop()


def test_wait_for_ignores_lines_before_last_ready(fake):
    # Regresi r33: token "reloading" milik fase control (SEBELUM restart)
    # tidak boleh match lagi setelah wait_ready() — match basi membuat
    # predikat selalu-True dan mendorong model membalik logika.
    app = App(fake("i.py", READY_RELOAD), ready_token="APP READY",
              interval=0.1, settle=0.1)
    app.start(timeout=10)
    try:
        assert app.wait_ready(timeout=5) is True   # restart terlihat
        assert app.wait_for("reloading", timeout=0.6) is False  # basi ≠ match
    finally:
        app.stop()


def test_wait_for_consumes_matched_line(fake):
    # Dua wait_for token sama = dua kejadian berbeda (pola hitung-kejadian).
    app = App(fake("j.py", READY_RELOAD), ready_token="APP READY",
              interval=0.1, settle=0.1)
    app.start(timeout=10)
    try:
        assert app.wait_for("reloading", timeout=5) is True
        assert app.wait_for("reloading", timeout=0.6) is False  # sudah dikonsumsi
    finally:
        app.stop()


def test_start_raises_when_never_ready(fake):
    app = App(fake("f.py", NEVER_READY), ready_token="APP READY",
              interval=0.1, settle=0.1)
    with pytest.raises(RuntimeError):
        app.start(timeout=1)
    assert app.poll() is not None  # child sudah dimatikan


def test_start_raises_fast_when_child_exits(fake):
    app = App(fake("g.py", EXIT_EARLY), ready_token="APP READY",
              interval=0.1, settle=0.1)
    t0 = time.time()
    with pytest.raises(RuntimeError):
        app.start(timeout=10)
    assert time.time() - t0 < 5  # tidak menunggu timeout penuh


def test_stop_terminates_child(fake):
    app = App(fake("h.py", READY_ONCE), ready_token="APP READY",
              interval=0.1, settle=0.1)
    app.start(timeout=10)
    app.stop()
    assert app.poll() is not None


def test_module_is_python36_compatible():
    src = (Path(__file__).parents[1] / "harness" / "stages"
           / "pipe_runtime.py").read_text(encoding="utf-8")
    compile(src, "pipe_runtime.py", "exec")  # sanity parse
    # penjaga fitur >3.6 yang gampang kepeleset
    assert ":=" not in src, "walrus operator tidak ada di py3.6"
    assert "text=True" not in src, "text= adalah alias 3.7+; pakai universal_newlines"
    assert "capture_output" not in src, "capture_output adalah 3.7+"
    assert "from __future__ import annotations" not in src, \
        "future-flag annotations baru ada di py3.7"
