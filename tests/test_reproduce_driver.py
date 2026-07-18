"""Test driver REPRODUCE Gemma — robustness eksekusi docker.

Lahir dari crash run r7 (11422): repro.py model spawn runserver dan hang
>180 s; subprocess.TimeoutExpired tidak ditangkap -> seluruh driver mati
tanpa event abort (kontrak docs/kontrak-output.md §8).
"""
import json
import subprocess
from pathlib import Path

import pytest

from harness.emit import Emitter
from harness.stages.run_reproduce_gemma import docker_exec, emit_abort


class _RunRecorder:
    """Pengganti subprocess.run: raise TimeoutExpired di call pertama,
    rekam call berikutnya (recovery restart)."""

    def __init__(self, stdout="partial out\n", stderr=""):
        self.calls = []
        self._first = True
        self._stdout = stdout
        self._stderr = stderr

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if self._first:
            self._first = False
            exc = subprocess.TimeoutExpired(argv, kwargs.get("timeout"))
            exc.stdout = self._stdout
            exc.stderr = self._stderr
            raise exc
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")


def test_docker_exec_timeout_returns_124_with_note(monkeypatch):
    rec = _RunRecorder()
    monkeypatch.setattr(subprocess, "run", rec)
    out, code = docker_exec("c1", "python /testbed/.pipe/repro.py", timeout=5)
    assert code == 124
    assert "partial out" in out
    assert "timed out after 5s" in out
    assert "restarted" in out  # model diberi tahu sandbox di-restart


def test_docker_exec_timeout_restarts_container(monkeypatch):
    rec = _RunRecorder()
    monkeypatch.setattr(subprocess, "run", rec)
    docker_exec("c1", "sleep 999", timeout=5)
    assert any("restart" in argv for argv in rec.calls[1:])


def test_docker_exec_timeout_tolerates_bytes_and_none(monkeypatch):
    rec = _RunRecorder(stdout=b"bytes out", stderr=None)
    monkeypatch.setattr(subprocess, "run", rec)
    out, code = docker_exec("c1", "x", timeout=5)
    assert code == 124
    assert "bytes out" in out


def test_driver_module_has_no_unresolved_names():
    # Regresi r19: retry_reason dipakai di main() tapi tak di-import ->
    # NameError baru meledak saat runtime. Kompilasi + audit nama global
    # fungsi-fungsi modul menangkapnya tanpa menjalankan docker.
    import ast
    import builtins
    import harness.stages.run_reproduce_gemma as drv
    tree = ast.parse(Path(drv.__file__).read_text(encoding="utf-8"))

    defined = set(dir(builtins)) | set(vars(drv).keys())
    loads = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            (loads if isinstance(n.ctx, ast.Load) else defined).add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(n.name)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                a = n.args
                for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs,
                            *([a.vararg] if a.vararg else []),
                            *([a.kwarg] if a.kwarg else [])]:
                    defined.add(arg.arg)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            defined.add(n.name)
        elif isinstance(n, ast.alias):
            defined.add((n.asname or n.name).split(".")[0])

    missing = loads - defined
    assert not missing, f"nama tak ter-resolve: {sorted(missing)}"


def test_docker_write_file_sends_lf_only_bytes(monkeypatch):
    # Bug nyata r15: text=True di Windows menerjemahkan \n -> \r\n saat
    # menulis ke pipe docker; pattern file grep berakhiran \r -> verifikasi
    # PASS_OBSERVABLE selalu MISSING terhadap source LF (kontrak §2: byte
    # \r di file adalah BUG).
    import harness.stages.run_reproduce_gemma as drv
    captured = {}

    def fake_run(argv, **kwargs):
        captured["input"] = kwargs.get("input")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    drv.docker_write_file("c1", "/tmp/x", "line1\nline2\r\nline3\n")
    assert isinstance(captured["input"], bytes)
    assert b"\r" not in captured["input"]
    assert captured["input"] == b"line1\nline2\nline3\n"


def test_observable_in_container_found(monkeypatch):
    import harness.stages.run_reproduce_gemma as drv
    monkeypatch.setattr(drv, "docker_write_file", lambda c, p, b: None)
    monkeypatch.setattr(drv, "docker_exec",
                        lambda c, cmd, timeout=60: ("FOUND\n", 0))
    assert drv.observable_in_container("c1", "changed, reloading.") is True


def test_observable_in_container_missing(monkeypatch):
    import harness.stages.run_reproduce_gemma as drv
    monkeypatch.setattr(drv, "docker_write_file", lambda c, p, b: None)
    monkeypatch.setattr(drv, "docker_exec",
                        lambda c, cmd, timeout=60: ("MISSING\n", 0))
    assert drv.observable_in_container("c1", "Detected change") is False


def test_emit_abort_writes_event_verdict_and_run_end(tmp_path):
    em = Emitter(tmp_path, "r-dev", "django__django-11422", 99)
    em.run_start()
    emit_abort(em, "driver crash: boom")

    events = [json.loads(l) for l in
              (em.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[-1]["event"] == "abort"
    assert events[-1]["detail"]["reason"] == "driver crash: boom"

    verdict = json.loads((em.run_dir / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["wall"] == "abort"

    runs = [json.loads(l) for l in
            (em.campaign_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert runs[-1]["event"] == "end"
    assert runs[-1]["wall"] == "abort"
