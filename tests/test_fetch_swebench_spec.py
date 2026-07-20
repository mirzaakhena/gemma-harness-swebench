"""Test freeze spec SWE-bench per case (tanpa network)."""
import json

from eval.fetch_swebench_spec import spec_from_row, write_spec

ROW = {"instance_id": "django__django-99999", "repo": "django/django",
       "version": "3.0", "base_commit": "abc123",
       "environment_setup_commit": "def456",
       "problem_statement": "bug report text", "patch": "--- a/x.py\n",
       "test_patch": "--- a/tests/foo/tests.py\n+++ b/tests/foo/tests.py\n",
       "FAIL_TO_PASS": "[\"test_a (foo.tests.FooTest)\"]",
       "PASS_TO_PASS": "[\"test_b (foo.tests.FooTest)\"]"}


def test_spec_from_row_decodes_lists_and_adds_provenance():
    spec = spec_from_row(dict(ROW), dataset="princeton-nlp/SWE-bench_Lite")
    assert spec["FAIL_TO_PASS"] == ["test_a (foo.tests.FooTest)"]
    assert spec["PASS_TO_PASS"] == ["test_b (foo.tests.FooTest)"]
    assert spec["_dataset"] == "princeton-nlp/SWE-bench_Lite"
    assert spec["_fetched_at"]
    assert spec["base_commit"] == "abc123"  # row lain ikut beku utuh


def test_spec_from_row_missing_key_raises():
    row = dict(ROW)
    del row["test_patch"]
    try:
        spec_from_row(row, dataset="d")
        raise AssertionError("should raise")
    except ValueError as e:
        assert "test_patch" in str(e)


def test_write_spec_utf8_lf_no_bom(tmp_path):
    spec = spec_from_row(dict(ROW), dataset="d")
    out = write_spec(spec, tmp_path)
    assert out == tmp_path / "django__django-99999" / "swebench_spec.json"
    raw = out.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert json.loads(raw.decode("utf-8"))["instance_id"] == ROW["instance_id"]


def test_main_with_injected_rows(tmp_path, capsys):
    from eval.fetch_swebench_spec import main
    rc = main(["--case", "django__django-99999", "--gold-root",
               str(tmp_path)], rows=[dict(ROW)])
    assert rc == 0
    assert (tmp_path / "django__django-99999" / "swebench_spec.json").is_file()


def test_main_unknown_case_errors(tmp_path):
    from eval.fetch_swebench_spec import main
    rc = main(["--case", "nope", "--gold-root", str(tmp_path)],
              rows=[dict(ROW)])
    assert rc == 1
