"""Test lapisan docker checker — subprocess di-mock, nol docker nyata."""
import subprocess
from pathlib import Path

import eval.swebench_runner as runner


def test_default_image():
    assert runner.default_image("django__django-13660") == (
        "ghcr.io/epoch-research/swe-bench.eval.x86_64."
        "django__django-13660:latest")


def test_run_eval_in_container_wiring(monkeypatch):
    calls = {}

    class FakeProc:
        returncode = 0
        stdout = "hello-log\n"
        stderr = "warn\n"

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        calls["kw"] = kw
        # tmpdir files only exist mid-call — the function cleans them up
        # (Fix #1) before returning, so assert on-disk state here.
        mount = cmd[4]
        tmpdir = Path(mount.split(":/patch-in")[0])
        assert (tmpdir / "eval.sh").is_file()
        for name in ("eval.sh", "fix.diff", "test_patch.diff"):
            raw = (tmpdir / name).read_bytes()
            assert not raw.startswith(b"\xef\xbb\xbf") and b"\r\n" not in raw
            assert raw.endswith(b"\n")
        return FakeProc()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    out = runner.run_eval_in_container("img:x", "#!/bin/bash\necho hi",
                                       "--- a/f\n", "--- a/t\n", timeout=99)
    assert out == {"log": "hello-log\nwarn\n", "exit": 0}
    cmd = calls["cmd"]
    assert cmd[:4] == ["docker", "run", "--rm", "-v"]
    mount = cmd[4]
    assert mount.endswith(":/patch-in:ro")
    tmpdir = Path(mount.split(":/patch-in")[0])
    assert cmd[5] == "img:x" and cmd[6:] == ["bash", "/patch-in/eval.sh"]
    assert calls["kw"]["timeout"] == 99
    # Fix #1: tmpdir is cleaned up after the call returns.
    assert not tmpdir.exists()


def test_run_eval_in_container_cleans_up_tmpdir_on_success(monkeypatch):
    captured = {}

    class FakeProc:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    def fake_run(cmd, **kw):
        mount = cmd[4]
        captured["tmpdir"] = Path(mount.split(":/patch-in")[0])
        return FakeProc()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.run_eval_in_container("img:x", "#!/bin/bash\necho hi",
                                 "--- a/f\n", "--- a/t\n", timeout=99)
    assert not captured["tmpdir"].exists()


def test_run_eval_in_container_timeout_translated(monkeypatch):
    def fake_run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"),
                                        output="partial output\n")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    out = runner.run_eval_in_container("img:x", "#!/bin/bash\necho hi",
                                       "--- a/f\n", "--- a/t\n", timeout=42)
    assert out["exit"] == 124
    assert "TIMEOUT" in out["log"]
    assert "partial output" in out["log"]
    assert "42" in out["log"]
