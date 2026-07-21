"""Test core pure checker SWE-bench L2 — tanpa docker, tanpa network."""
import locale

import pytest

from eval._swebench_compat import ensure_resource_shim

ensure_resource_shim()
from swebench.harness.constants import END_TEST_OUTPUT, START_TEST_OUTPUT

from eval.swebench_checker import (build_eval_script, grade_log, load_spec,
                                   summarize_report, write_gradeable_log_copy)

SPEC = {"instance_id": "django__django-99999", "repo": "django/django",
        "version": "3.0", "base_commit": "abc123",
        "environment_setup_commit": "abc123",
        "test_patch": ("diff --git a/tests/foo/tests.py b/tests/foo/tests.py\n"
                       "--- a/tests/foo/tests.py\n+++ b/tests/foo/tests.py\n"
                       "@@ -1 +1,2 @@\n pass\n+pass\n"),
        "FAIL_TO_PASS": ["test_a (foo.tests.FooTest)"],
        "PASS_TO_PASS": ["test_b (foo.tests.FooTest)"]}

DIFF = "--- a/django/x.py\n+++ b/django/x.py\n@@ -1 +1 @@\n-a\n+b\n"


def _log(body: str) -> str:
    return f"{START_TEST_OUTPUT}\n{body}\n{END_TEST_OUTPUT}\n"


@pytest.fixture(autouse=True)
def _no_network_requirements(monkeypatch):
    """grade_log() builds a real TestSpec via make_test_spec(), which for
    django/django (packages: requirements.txt) fetches requirements.txt over
    HTTP regardless of whether base_commit is real — stub it so tests never
    touch network (global constraint: NO network in tests)."""
    from swebench.harness.test_spec import python as _sb_python
    monkeypatch.setattr(_sb_python, "get_requirements_by_commit",
                        lambda repo, commit: "Django==3.0\n")


def test_load_spec_missing_file_mentions_fetch(tmp_path):
    with pytest.raises(FileNotFoundError) as e:
        load_spec(tmp_path / "swebench_spec.json")
    assert "fetch_swebench_spec" in str(e.value)


def test_build_eval_script_shape():
    script = build_eval_script(SPEC)
    assert "conda activate testbed" in script
    assert "git apply /patch-in/fix.diff" in script
    assert "git apply /patch-in/test_patch.diff" in script
    assert f"git checkout {SPEC['base_commit']} -- tests/foo/tests.py" in script
    assert START_TEST_OUTPUT in script and END_TEST_OUTPUT in script
    assert "runtests.py" in script          # test_cmd django dari peta resmi
    assert "foo" in script.split(START_TEST_OUTPUT)[1]  # direktif test


def test_build_eval_script_empty_test_patch_files_no_bare_checkout():
    """test_patch yang HANYA menambah file baru (`--- /dev/null`) bikin
    `tp_files = re.findall(r"--- a/(.*)", ...)` == [] — `git checkout
    {base_commit} {tp_files}` tanpa pathspec jadi checkout SELURUH tree
    (silent-misgrade class, temuan review final). Harus TIDAK PERNAH
    mengeluarkan `git checkout <base>` tanpa `--`/pathspec; wajib degradasi
    ke guard RESET_FAILED (case ini di luar populasi wajar: test_patch yang
    tak bisa di-reset)."""
    from swebench.harness.constants import RESET_FAILED
    spec = dict(SPEC)
    spec["test_patch"] = (
        "diff --git a/tests/foo/new_test.py b/tests/foo/new_test.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n+++ b/tests/foo/new_test.py\n"
        "@@ -0,0 +1,2 @@\n+pass\n+pass\n")
    script = build_eval_script(spec)
    assert f"git checkout {spec['base_commit']}" not in script
    assert RESET_FAILED in script


def test_build_eval_script_guards_checkout_and_test_patch_apply():
    """checkout base_commit dan apply test_patch tanpa guard bisa gagal
    diam-diam (file test stale/renamed, base_commit tak cocok) lalu lolos
    ke echo START_TEST_OUTPUT — grading salah baca log sbg hasil valid.
    Guard pakai marker RESMI swebench (bad_codes di get_logs_eval) supaya
    grade_log() balik patch_successfully_applied=False, bukan set -e (yang
    akan gugurkan END_TEST_OUTPUT saat test biasa gagal — P2P regressions
    butuh marker itu tetap muncul)."""
    from swebench.harness.constants import APPLY_PATCH_FAIL, RESET_FAILED
    script = build_eval_script(SPEC)
    assert "set -e" not in script  # test biasa gagal harus tetap emit END marker
    assert RESET_FAILED in script and "exit 3" in script
    assert APPLY_PATCH_FAIL in script and "exit 4" in script


def test_grade_log_resolved_true(tmp_path):
    log = tmp_path / "out.log"
    log.write_text(_log("test_a (foo.tests.FooTest) ... ok\n"
                        "test_b (foo.tests.FooTest) ... ok"),
                   encoding="utf-8")
    raw = grade_log(SPEC, DIFF, log)
    assert raw["patch_successfully_applied"] is True
    assert raw["resolved"] is True


def test_grade_log_p2p_regression(tmp_path):
    log = tmp_path / "out.log"
    log.write_text(_log("test_a (foo.tests.FooTest) ... ok\n"
                        "test_b (foo.tests.FooTest) ... FAIL"),
                   encoding="utf-8")
    raw = grade_log(SPEC, DIFF, log)
    assert raw["resolved"] is False
    assert raw["tests_status"]["PASS_TO_PASS"]["failure"] == [
        "test_b (foo.tests.FooTest)"]


# R4 (V-C): non-ASCII test output. U+2001 encodes to UTF-8 bytes E2 80 81;
# byte 0x81 is UNDEFINED in cp1252, so a bare open() of the UTF-8 log under the
# Windows default codec raises UnicodeDecodeError('charmap'). U+2603/U+0394 are
# extra chars unrepresentable in cp1252 (exercise errors="replace").
NON_ASCII = " ☃ astropy Δ output"


def test_gradeable_log_copy_readable_by_grader_without_unicode_crash(tmp_path):
    """swebench grading.py:58 reads the log with a bare open() → the platform
    default codec (cp1252 on Windows), which UnicodeDecodeError-crashes on
    non-ASCII astropy output (V-C). write_gradeable_log_copy must produce a copy
    the grader can read under that same default codec, while the original UTF-8
    artifact is left untouched."""
    log_text = _log("test_a (foo.tests.FooTest) ... ok\n" + NON_ASCII)

    # Reproduce the failure mode: a UTF-8 artifact read as cp1252 (the Windows
    # grader default) raises. Pin cp1252 explicitly so this holds on any OS.
    utf8_artifact = tmp_path / "swebench_test_output.log"
    utf8_artifact.write_text(log_text, encoding="utf-8", newline="\n")
    with pytest.raises(UnicodeDecodeError):
        with open(utf8_artifact, encoding="cp1252") as f:
            f.read()

    # Fix: a locale-encoded copy the grader reads with its default codec.
    grade_copy = write_gradeable_log_copy(
        log_text, tmp_path / "swebench_test_output.grade.log")
    assert grade_copy.is_file()
    # Bare open() == grader style == platform default (matches how the copy was
    # written) → round-trips with no UnicodeDecodeError on every platform.
    with open(grade_copy) as f:
        got = f.read()
    assert START_TEST_OUTPUT in got and END_TEST_OUTPUT in got
    assert "test_a (foo.tests.FooTest) ... ok" in got

    # Original artifact stays byte-for-byte UTF-8.
    assert utf8_artifact.read_text(encoding="utf-8") == log_text


def test_gradeable_log_copy_uses_locale_encoding_with_replace(tmp_path):
    """Copy is encoded with locale.getpreferredencoding(False), errors=replace —
    so encoding never raises even when chars are unrepresentable, and the file is
    valid under that codec (what the grader reads with)."""
    enc = locale.getpreferredencoding(False)
    dest = write_gradeable_log_copy(_log(NON_ASCII), tmp_path / "g.log")
    # Valid under the locale codec (strict decode succeeds — grader read is strict).
    dest.read_text(encoding=enc)
    # ASCII markers survive regardless of codec.
    assert START_TEST_OUTPUT in dest.read_text(encoding=enc)


def test_grade_log_no_markers_means_apply_failed(tmp_path):
    log = tmp_path / "out.log"
    log.write_text("FIX_APPLY_FAILED\n", encoding="utf-8")
    raw = grade_log(SPEC, DIFF, log)
    assert raw["patch_successfully_applied"] is False
    assert raw["resolved"] is False


def test_summarize_report_schema(tmp_path):
    log = tmp_path / "out.log"
    log.write_text(_log("test_a (foo.tests.FooTest) ... ok\n"
                        "test_b (foo.tests.FooTest) ... FAIL"),
                   encoding="utf-8")
    raw = grade_log(SPEC, DIFF, log)
    s = summarize_report(raw, SPEC, case="django__django-99999", rerun=1,
                         image="img:latest", spec_path="cases/gold/x.json",
                         log_rel="files/swebench_test_output.log",
                         checked_at="2026-07-20T00:00:00+00:00")
    assert s["case"] == "django__django-99999" and s["rerun"] == 1
    assert s["resolved"] is False
    assert s["f2p_passed"] == ["test_a (foo.tests.FooTest)"]
    assert s["f2p_failed"] == []
    assert s["p2p_failed"] == ["test_b (foo.tests.FooTest)"]
    assert s["p2p_passed_count"] == 0
    assert s["image"] == "img:latest" and s["checked_at"]


def _mk_run(tmp_path, campaign="f-dev", case="django__django-99999",
            rerun=1, with_diff=True):
    run_dir = tmp_path / "artifacts" / campaign / f"{campaign}--{case}--r{rerun}"
    (run_dir / "files").mkdir(parents=True)
    if with_diff:
        (run_dir / "files" / "fix.diff").write_text(DIFF, encoding="utf-8")
    (run_dir / "verdict.json").write_text("{\"sentinel\": 1}",
                                          encoding="utf-8")
    return run_dir


def _spec_file(tmp_path):
    import json as _json
    p = tmp_path / "swebench_spec.json"
    p.write_text(_json.dumps(SPEC), encoding="utf-8")
    return p


def test_run_checker_happy_path(tmp_path):
    from eval.swebench_checker import run_checker
    run_dir = _mk_run(tmp_path)
    spec_path = _spec_file(tmp_path)

    def fake_runner(image, script, fix_diff, test_patch, timeout):
        assert "conda activate testbed" in script
        return {"log": _log("test_a (foo.tests.FooTest) ... ok\n"
                            "test_b (foo.tests.FooTest) ... ok"),
                "exit": 0}

    rc, out = run_checker(
        case="django__django-99999", rerun=1, campaign="f-dev",
        artifacts=str(tmp_path / "artifacts"), image="img:x",
        spec_path=str(spec_path), timeout=60, runner=fake_runner)
    assert rc == 0 and out["resolved"] is True
    import json as _json
    written = _json.loads((run_dir / "swebench_eval.json")
                          .read_text(encoding="utf-8"))
    assert written["resolved"] is True
    assert written["image"] == "img:x"
    assert (run_dir / "files" / "swebench_test_output.log").is_file()
    # verdict.json TIDAK disentuh (boundary — aturan inti spec)
    assert (run_dir / "verdict.json").read_text(encoding="utf-8") == (
        "{\"sentinel\": 1}")


def test_run_checker_missing_diff(tmp_path):
    from eval.swebench_checker import run_checker
    _mk_run(tmp_path, with_diff=False)
    rc, out = run_checker(
        case="django__django-99999", rerun=1, campaign="f-dev",
        artifacts=str(tmp_path / "artifacts"), image="img:x",
        spec_path=str(_spec_file(tmp_path)), timeout=60,
        runner=lambda *a, **k: {"log": "", "exit": 0})
    assert rc == 1 and "fix.diff" in out["error"]


def test_run_checker_grade_failure_writes_log_not_eval_json(tmp_path,
                                                             monkeypatch):
    """grade_log() calls make_test_spec(), which for django does a live
    requests.get for requirements.txt (a field grading never uses) — an
    infra hiccup there would otherwise crash run_checker mid-run. It must
    instead degrade to an error dict, still persist the raw log for
    debugging, skip the (now misleading) swebench_eval.json, and leave
    verdict.json/events.jsonl untouched (checker/model boundary)."""
    import eval.swebench_checker as checker_mod
    run_dir = _mk_run(tmp_path)
    spec_path = _spec_file(tmp_path)

    def fake_runner(image, script, fix_diff, test_patch, timeout):
        return {"log": _log("test_a (foo.tests.FooTest) ... ok"), "exit": 0}

    def fake_grade_log(spec, fix_diff_text, log_path):
        raise RuntimeError("requirements.txt fetch failed")

    monkeypatch.setattr(checker_mod, "grade_log", fake_grade_log)

    rc, out = checker_mod.run_checker(
        case="django__django-99999", rerun=1, campaign="f-dev",
        artifacts=str(tmp_path / "artifacts"), image="img:x",
        spec_path=str(spec_path), timeout=60, runner=fake_runner)

    assert rc == 1
    assert out["error"] == "swebench eval failed"
    assert "requirements.txt fetch failed" in out["detail"]
    assert out["case"] == "django__django-99999" and out["rerun"] == 1
    assert (run_dir / "files" / "swebench_test_output.log").read_text(
        encoding="utf-8") == _log("test_a (foo.tests.FooTest) ... ok")
    assert not (run_dir / "swebench_eval.json").exists()
    assert (run_dir / "verdict.json").read_text(encoding="utf-8") == (
        "{\"sentinel\": 1}")
