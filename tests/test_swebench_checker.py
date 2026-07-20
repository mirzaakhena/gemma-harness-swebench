"""Test core pure checker SWE-bench L2 — tanpa docker, tanpa network."""
import pytest

from eval._swebench_compat import ensure_resource_shim

ensure_resource_shim()
from swebench.harness.constants import END_TEST_OUTPUT, START_TEST_OUTPUT

from eval.swebench_checker import (build_eval_script, grade_log, load_spec,
                                   summarize_report)

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
    assert f"git checkout {SPEC['base_commit']} tests/foo/tests.py" in script
    assert START_TEST_OUTPUT in script and END_TEST_OUTPUT in script
    assert "runtests.py" in script          # test_cmd django dari peta resmi
    assert "foo" in script.split(START_TEST_OUTPUT)[1]  # direktif test


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
