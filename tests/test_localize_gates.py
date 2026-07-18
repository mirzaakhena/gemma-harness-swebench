"""Test gate mekanis stage LOCALIZE (pure-function).

Kontrak: docs/kontrak-output.md §10 (satu format localize.md) + lever P25:
rentang lines wajib sempit (<=200), file harus ada, rentang di dalam file.
"""
import pytest

from harness.stages.localize_gates import (
    LocalizeResult,
    evaluate_localize_gates,
    parse_localize_md,
)

MD_OK = """chosen: 1
file: django/utils/autoreload.py
lines: 105-130
what: Guard __spec__ None menendang entry-point __main__ dari daftar watch.
why: iter_modules_and_files men-skip module tanpa __spec__, padahal __main__ selalu begitu.
evidence: Fungsi iter_modules_and_files (baris ~115) melakukan `continue` saat getattr(module, '__spec__', None) is None; repro menunjukkan manage.py hilang dari watched_files().
"""


def test_parse_localize_md_ok():
    s = parse_localize_md(MD_OK)
    assert s["chosen"] == "1"
    assert s["file"] == "django/utils/autoreload.py"
    assert s["lines"] == (105, 130)
    assert s["what"].startswith("Guard")
    assert s["evidence"].startswith("Fungsi")


def test_parse_localize_md_missing_slots_lists_all():
    with pytest.raises(ValueError) as e:
        parse_localize_md("chosen: 1\nfile: x.py\n")
    msg = str(e.value)
    assert "lines" in msg and "what" in msg and "why" in msg and "evidence" in msg


def test_parse_localize_md_bad_lines_format():
    with pytest.raises(ValueError, match="lines"):
        parse_localize_md(MD_OK.replace("lines: 105-130", "lines: seluruh file"))


def test_parse_localize_md_lines_reversed_rejected():
    with pytest.raises(ValueError, match="lines"):
        parse_localize_md(MD_OK.replace("lines: 105-130", "lines: 130-105"))


def test_gates_all_pass():
    r = evaluate_localize_gates(MD_OK, file_exists=True, file_line_count=640)
    assert isinstance(r, LocalizeResult)
    assert r.verdict == "pass"
    assert r.failures == []


def test_gate_span_too_wide_rejected():
    md = MD_OK.replace("lines: 105-130", "lines: 1-1500")
    r = evaluate_localize_gates(md, file_exists=True, file_line_count=2000)
    assert r.verdict == "fail"
    assert any("rentang" in f for f in r.failures)


def test_gate_file_not_exists_rejected():
    r = evaluate_localize_gates(MD_OK, file_exists=False, file_line_count=None)
    assert r.verdict == "fail"
    assert any("tidak ada" in f for f in r.failures)


def test_gate_lines_beyond_eof_rejected():
    r = evaluate_localize_gates(MD_OK, file_exists=True, file_line_count=100)
    assert r.verdict == "fail"
    assert any("melewati akhir file" in f for f in r.failures)


def test_gate_malformed_md_is_syntax_fail():
    r = evaluate_localize_gates("chosen: 1\n", file_exists=True, file_line_count=100)
    assert r.verdict == "syntax-fail"
