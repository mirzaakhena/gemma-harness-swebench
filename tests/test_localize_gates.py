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


GOLD_PATCH = """diff --git a/django/utils/autoreload.py b/django/utils/autoreload.py
--- a/django/utils/autoreload.py
+++ b/django/utils/autoreload.py
@@ -110,6 +110,10 @@ def iter_modules_and_files(modules, extra_files):
     for module in modules:
+        if getattr(module, "__spec__", None) is None:
+            continue
@@ -220,3 +224,5 @@ def tail
     x = 1
+    y = 2
diff --git a/tests/utils_tests/test_autoreload.py b/tests/utils_tests/test_autoreload.py
--- a/tests/utils_tests/test_autoreload.py
+++ b/tests/utils_tests/test_autoreload.py
@@ -1,3 +1,4 @@
+import x
"""


def test_gold_touched_files_parses_b_side():
    # L2 LOCALIZE (keputusan Mirza 2026-07-19): ground truth = file yang
    # disentuh gold patch; parser membaca sisi b/ dari unified diff.
    from eval.localize_gold_eval import gold_touched_files
    assert gold_touched_files(GOLD_PATCH) == {
        "django/utils/autoreload.py",
        "tests/utils_tests/test_autoreload.py",
    }


def test_gold_touched_files_ignores_dev_null():
    from eval.localize_gold_eval import gold_touched_files
    patch = ("diff --git a/old.py b/old.py\n--- a/old.py\n+++ /dev/null\n"
             "@@ -1 +0,0 @@\n-x\n")
    assert gold_touched_files(patch) == {"old.py"}


def test_gold_line_ranges_for_file():
    # Overlap rentang baris = telemetri L3 advisory (bukan vonis) — "gaya
    # boleh beda" ala flip test; rentang diambil dari sisi baru (+c,d).
    from eval.localize_gold_eval import gold_line_ranges
    ranges = gold_line_ranges(GOLD_PATCH, "django/utils/autoreload.py")
    assert ranges == [(110, 119), (224, 228)]


def test_evaluate_l2_file_match_pass_and_wrong_logic():
    # Vonis L2 mekanis: file: di localize.md harus anggota himpunan file
    # gold; mismatch -> wrong-logic (padanan flip-fail di REPRODUCE).
    from eval.localize_gold_eval import evaluate_localize_l2
    ok = evaluate_localize_l2("django/utils/autoreload.py", GOLD_PATCH,
                              lines=(105, 130))
    assert ok.file_match is True
    assert ok.line_overlap is True   # 105-130 overlap hunk 110-119
    bad = evaluate_localize_l2("django/core/handlers/base.py", GOLD_PATCH,
                               lines=(1, 10))
    assert bad.file_match is False
    assert bad.line_overlap is None  # file salah -> overlap tak bermakna


def test_evaluate_l2_no_overlap_is_advisory_only():
    from eval.localize_gold_eval import evaluate_localize_l2
    r = evaluate_localize_l2("django/utils/autoreload.py", GOLD_PATCH,
                             lines=(500, 600))
    assert r.file_match is True      # tetap match — vonis dari file saja
    assert r.line_overlap is False   # advisory: situs beda dgn hunk gold


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
    assert any("range" in f for f in r.failures)


def test_gate_file_not_exists_rejected():
    r = evaluate_localize_gates(MD_OK, file_exists=False, file_line_count=None)
    assert r.verdict == "fail"
    assert any("does not exist" in f for f in r.failures)


def test_gate_lines_beyond_eof_rejected():
    r = evaluate_localize_gates(MD_OK, file_exists=True, file_line_count=100)
    assert r.verdict == "fail"
    assert any("beyond the end of file" in f for f in r.failures)


def test_gate_malformed_md_is_syntax_fail():
    r = evaluate_localize_gates("chosen: 1\n", file_exists=True, file_line_count=100)
    assert r.verdict == "syntax-fail"


# --- drift-guard kontrak localize_prompt.md (Lever L#1, Mirza 2026-07-19) ---

def _contract_text():
    from pathlib import Path
    import harness.stages.localize_gates as lg
    return (Path(lg.__file__).parent / "localize_prompt.md").read_text(
        encoding="utf-8")


def test_contract_has_definition_site_ownership_rule():
    # Kelas salah-lapisan batch L pertama (11964 1/3 alternative-fix-site,
    # 11797 0/3 manifestation-layer): model paham mekanisme tapi menunjuk
    # infrastruktur generik/lapisan manifestasi. Signal-less di dunia
    # product -> lever = rule kontrak (CORE), bukan detector.
    text = _contract_text()
    assert "OWNS the wrong decision" in text
    assert "one level upstream" in text


def test_contract_probe_rule_covers_layer_discrimination():
    # 11797: model berhenti di file yang tampil di jalur eksekusi tanpa
    # probe pembeda antar lapisan kandidat.
    import re
    text = re.sub(r"\s+", " ", _contract_text())
    assert "not evidence that the fix belongs there" in text
