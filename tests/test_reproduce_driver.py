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


def test_tool_call_marker_triggers_strong_reminder():
    """R3/KH-12: reply memakai protokol tool-call native tanpa fence -> driver
    REPRODUCE mengarahkan model ke fenced block yang sah (English)."""
    from harness.stages.gemma_protocol import no_action_feedback
    import harness.stages.run_reproduce_gemma as rdrv
    reply = '<|tool_call|>\n{"name": "write_file", "path": "repro.py"}'
    msg = no_action_feedback(reply, rdrv._ACTION_FORMS)
    assert "```file:" in msg and "```bash" in msg
    for w in ("kamu", "jalankan", "tulis", "berkas"):
        assert w not in msg.lower()


# --- lever infra-abort (KH-22): preflight, crash transport, salvage ---------
# Insiden 15902 r4-r9 & 14855 r4-r9: endpoint mati -> driver crash tervonis
# repro-missing biasa; varian terburuk 14855 r7: 21 turn kerja nyata
# TERTELAN karena files/ tak tersalin sebelum crash.

import sys

import harness.stages.chat_transport as ct
import harness.stages.run_reproduce_gemma as drv


def _setup_main(monkeypatch, tmp_path, *, docker_exec=None):
    problem = tmp_path / "problem.txt"
    problem.write_text("the bug", encoding="utf-8")
    art = tmp_path / "artifacts"
    monkeypatch.setattr(drv.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0,
                                                                    "", ""))
    monkeypatch.setattr(drv, "docker_write_file", lambda *a, **k: None)
    if docker_exec is None:
        def docker_exec(container, cmd, timeout=180):
            if "repro.py" in cmd:
                return "print('salvaged')\n", 0
            return "", 0
    monkeypatch.setattr(drv, "docker_exec", docker_exec)
    monkeypatch.setattr(sys, "argv", [
        "run_reproduce_gemma.py", "--case", "django__django-15902",
        "--rerun", "4", "--image", "img", "--artifacts", str(art),
        "--problem-file", str(problem), "--max-turns", "5"])
    return art / "r-dev" / "r-dev--django__django-15902--r4"


def _events(run_dir):
    return [json.loads(l) for l in
            (run_dir / "events.jsonl").read_text(encoding="utf-8")
            .splitlines()]


def test_preflight_failure_exits_fast_without_container(monkeypatch,
                                                        tmp_path):
    run_dir = _setup_main(monkeypatch, tmp_path)
    docker_calls = []
    monkeypatch.setattr(drv.subprocess, "run",
                        lambda argv, **k: docker_calls.append(argv))
    monkeypatch.setattr(
        drv, "preflight_endpoint",
        lambda *a, **k: (_ for _ in ()).throw(
            ct.ChatTransportError("preflight ping http://x/v1/models "
                                  "failed after 2 attempts")))
    monkeypatch.setattr(
        drv, "chat_with_retry",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("model tak boleh dipanggil saat preflight gagal")))
    assert drv.main() == 1
    assert not docker_calls  # container/model TIDAK dibakar
    marker = json.loads((run_dir / "infra_abort.json")
                        .read_text(encoding="utf-8"))
    assert marker["reason"] == "preflight"
    assert marker["stage"] == "reproduce"
    assert marker["turns_model_used"] == 0
    events = _events(run_dir)
    aborts = [e for e in events if e["event"] == "abort"]
    assert aborts
    assert aborts[-1]["detail"]["reason"].startswith(
        "infra transport failure")
    v = json.loads((run_dir / "verdict.json").read_text(encoding="utf-8"))
    assert v["wall"] == "abort"


def test_transport_crash_mid_run_writes_marker_and_salvages(monkeypatch,
                                                            tmp_path):
    run_dir = _setup_main(monkeypatch, tmp_path)
    monkeypatch.setattr(drv, "preflight_endpoint", lambda *a, **k: None)
    calls = []

    def chatting(endpoint, model, messages, **kw):
        calls.append(1)
        if len(calls) == 1:
            return "let me look around first."
        raise ct.ChatTransportError(
            "model endpoint transport failure after 4 attempts: "
            "URLError(TimeoutError(10060))")

    monkeypatch.setattr(drv, "chat_with_retry", chatting)
    assert drv.main() == 1
    marker = json.loads((run_dir / "infra_abort.json")
                        .read_text(encoding="utf-8"))
    assert marker["stage"] == "reproduce"
    assert marker["turns_model_used"] == 1  # model AKTIF 1 turn sebelum mati
    assert "10060" in marker["detail"]
    # Salvage best-effort: kerja nyata di container TIDAK tertelan
    # (pelajaran 14855 r7 — 21 turn hilang karena files/ kosong).
    assert (run_dir / "files" / "repro.py").read_text(
        encoding="utf-8") == "print('salvaged')\n"
    aborts = [e for e in _events(run_dir) if e["event"] == "abort"]
    assert aborts
    assert aborts[-1]["detail"]["reason"].startswith(
        "infra transport failure")
    assert "repro.py" in aborts[-1]["detail"]["salvaged"]


def test_salvage_failure_never_changes_exit_path(monkeypatch, tmp_path):
    def broken_exec(container, cmd, timeout=180):
        raise RuntimeError("docker daemon is gone")

    run_dir = _setup_main(monkeypatch, tmp_path, docker_exec=broken_exec)
    monkeypatch.setattr(drv, "preflight_endpoint", lambda *a, **k: None)
    monkeypatch.setattr(
        drv, "chat_with_retry",
        lambda *a, **k: (_ for _ in ()).throw(
            ct.ChatTransportError("transport down")))
    assert drv.main() == 1  # salvage gagal MASIH exit jujur, bukan crash lain
    marker = json.loads((run_dir / "infra_abort.json")
                        .read_text(encoding="utf-8"))
    assert marker["stage"] == "reproduce"
    aborts = [e for e in _events(run_dir) if e["event"] == "abort"]
    assert aborts and aborts[-1]["detail"]["salvaged"] == []
