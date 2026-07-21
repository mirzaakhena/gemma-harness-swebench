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


# --- LV-09: dunia KERJA FIX & LOCALIZE juga wajib menerima pipe_runtime -----
# (R1 Gelombang 1). Sebelumnya hanya dunia segar gate yang benar; container
# kerja FIX bolong (588x ImportError di f-dev--11910--r1) dan L idem.

def test_fix_ship_repro_includes_pipe_runtime_when_present(monkeypatch, tmp_path):
    from harness.stages import run_fix_gemma as fixd
    written = {}
    monkeypatch.setattr(fixd, "docker_write_file",
                        lambda c, path, body: written.setdefault(path, body))
    (tmp_path / "repro.py").write_text("from pipe_runtime import App\n",
                                       encoding="utf-8")
    (tmp_path / "pipe_runtime.py").write_text("class App: pass\n",
                                              encoding="utf-8")
    shipped = fixd.ship_repro_to_container("c", tmp_path)
    assert shipped == ["repro.py", "pipe_runtime.py"]
    assert "/testbed/.pipe/repro.py" in written
    assert "/testbed/.pipe/pipe_runtime.py" in written


def test_fix_ship_repro_without_pipe_runtime(monkeypatch, tmp_path):
    from harness.stages import run_fix_gemma as fixd
    written = {}
    monkeypatch.setattr(fixd, "docker_write_file",
                        lambda c, path, body: written.setdefault(path, body))
    (tmp_path / "repro.py").write_text("print('x')\n", encoding="utf-8")
    shipped = fixd.ship_repro_to_container("c", tmp_path)
    assert shipped == ["repro.py"]
    assert "/testbed/.pipe/pipe_runtime.py" not in written


def test_localize_driver_ships_pipe_runtime_source_line():
    # Guard statis: driver L menulis pipe_runtime kondisional dari input_dir
    # (jalur main() butuh docker; cukup pastikan wiring-nya ada & benar arah).
    import inspect
    from harness.stages import run_localize_gemma as locd
    src = inspect.getsource(locd.main)
    assert '/testbed/.pipe/pipe_runtime.py' in src
    assert 'input_dir / "pipe_runtime.py"' in src
