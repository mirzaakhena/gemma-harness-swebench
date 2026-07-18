"""Test wiring pipe_runtime — helper harus sampai ke SEMUA dunia eksekusi.

Tiga jalur yang wajib membawa /testbed/.pipe/pipe_runtime.py:
1. container kerja model (driver menulis saat run start),
2. fresh sandbox pre-check mid-loop (fresh_sandbox_output),
3. container gate/flip (repro_sandbox_runner.run_once — mount files/).
Tanpa salah satunya, `from pipe_runtime import App` lolos di satu dunia
tapi ImportError di dunia lain — kelas bug lintas-dunia (preseden r15/r16).
"""
import json
from pathlib import Path

from harness.stages import repro_sandbox_runner
from harness.stages import run_reproduce_gemma as driver


def test_run_once_copies_pipe_runtime_when_present(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd

        class P:
            stdout = ""
            stderr = ""
            returncode = 0
        return P()

    monkeypatch.setattr(repro_sandbox_runner.subprocess, "run", fake_run)
    repro_sandbox_runner.run_once("img", r"C:\some\files", 30)
    bash = captured["cmd"][-1]
    assert "pipe_runtime.py" in bash
    assert "cp /pipe-in/repro.py" in bash


def test_fresh_sandbox_output_ships_pipe_runtime(monkeypatch, tmp_path):
    captured = {}

    def fake_docker_exec(container, cmd, timeout=180):
        return ("print('hi')", 0)

    def fake_run_once(image, repro_host_dir, timeout,
                      patch_host_dir=None, patch_name=None):
        captured["dir"] = Path(repro_host_dir)
        captured["names"] = sorted(
            p.name for p in Path(repro_host_dir).iterdir())
        return {"output": "REPRO_STATUS: FAIL", "exit": 0}

    monkeypatch.setattr(driver, "docker_exec", fake_docker_exec)
    monkeypatch.setattr(driver, "run_once", fake_run_once)
    out, code = driver.fresh_sandbox_output("some-container", "img")
    assert code == 0
    assert "repro.py" in captured["names"]
    assert "pipe_runtime.py" in captured["names"]


def test_driver_ships_runtime_source_exists():
    # Sumber kanonik yang dikirim driver ke container + files/ run.
    assert driver.RUNTIME_PATH.is_file()
    src = driver.RUNTIME_PATH.read_text(encoding="utf-8")
    assert "class App" in src
