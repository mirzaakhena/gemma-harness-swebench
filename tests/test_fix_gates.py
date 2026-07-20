"""Test gate mekanis stage FIX (pure-function) — evaluator patch tunggal.

Spec 2026-07-20 §4/§7: satu standar kebenaran untuk pre-check driver DAN
gate L1: diff non-empty, hanya menyentuh file kandidat, repro pair 2x PASS
(exact_status). fix.md: slot interpretif model + slot mekanis harness
(pola compose_repro_md)."""
import pytest

from harness.stages.fix_gates import (
    FixPatchResult,
    compose_fix_md,
    diff_touched_files,
    evaluate_pair_outputs,
    fix_rejection_message,
    parse_fix_md,
    patch_static_result,
)

DIFF = """diff --git a/django/db/models/enums.py b/django/db/models/enums.py
--- a/django/db/models/enums.py
+++ b/django/db/models/enums.py
@@ -60,7 +60,13 @@ def values(cls):
+    def __str__(self):
+        return str(self.value)
"""

DIFF_TWO_FILES = DIFF + """diff --git a/django/db/models/base.py b/django/db/models/base.py
--- a/django/db/models/base.py
+++ b/django/db/models/base.py
@@ -1,3 +1,4 @@
+import x
"""

CAND = "django/db/models/enums.py"


def test_diff_touched_files():
    assert diff_touched_files(DIFF) == {"django/db/models/enums.py"}
    assert diff_touched_files(DIFF_TWO_FILES) == {
        "django/db/models/enums.py", "django/db/models/base.py"}


def test_static_empty_diff_rejected():
    r = patch_static_result("", CAND)
    assert r is not None and r.ok is False and r.reason == "empty-diff"


def test_static_off_candidate_rejected_names_stray_file():
    r = patch_static_result(DIFF_TWO_FILES, CAND)
    assert r is not None and r.reason == "off-candidate-files"
    assert "django/db/models/base.py" in r.failures[0]


def test_static_clean_diff_passes():
    assert patch_static_result(DIFF, CAND) is None


def test_static_tolerates_leading_slash_candidate():
    assert patch_static_result(DIFF, "/django/db/models/enums.py") is None


def test_pair_pass_pass_ok():
    r = evaluate_pair_outputs(DIFF, CAND,
                              "REPRO_STATUS: PASS\n", 0,
                              "REPRO_STATUS: PASS\n", 0)
    assert r.ok is True and r.reason is None
    assert r.status1 == "PASS" and r.status2 == "PASS"


def test_pair_fail_rejected_with_structured_statuses():
    r = evaluate_pair_outputs(DIFF, CAND,
                              "REPRO_STATUS: FAIL\n", 0,
                              "REPRO_STATUS: PASS\n", 0)
    assert r.ok is False and r.reason == "pair-not-pass"
    assert r.status1 == "FAIL" and r.status2 == "PASS"
    assert r.exit1 == 0 and r.run1_tail


def test_pair_exact_line_standard():
    # standar tunggal exact_status: token ber-embel-embel BUKAN PASS.
    r = evaluate_pair_outputs(DIFF, CAND,
                              "REPRO_STATUS: PASS (probably)\n", 0,
                              "REPRO_STATUS: PASS\n", 0)
    assert r.ok is False


def test_pair_timeout_reason():
    r = evaluate_pair_outputs(DIFF, CAND, "x\n[runner] TIMEOUT", -1, "", -1)
    assert r.ok is False and r.reason == "timeout"


def test_rejection_messages_are_english_and_concrete():
    msgs = [
        fix_rejection_message(patch_static_result("", CAND), CAND),
        fix_rejection_message(patch_static_result(DIFF_TWO_FILES, CAND), CAND),
        fix_rejection_message(
            evaluate_pair_outputs(DIFF, CAND, "REPRO_STATUS: FAIL\n", 0,
                                  "boom\n", 1), CAND),
        fix_rejection_message(
            evaluate_pair_outputs(DIFF, CAND, "[runner] TIMEOUT", -1,
                                  "", -1), CAND),
    ]
    for m in msgs:
        assert m.startswith("Not done yet:")
        for word in ("Belum", "kamu", "dulu", "serahkan", "jalankan"):
            assert word not in m, f"pesan ke model masih ber-Indonesia: {m!r}"
    assert CAND in msgs[0]                        # fakta konkret: edit site
    assert "django/db/models/base.py" in msgs[1]  # fakta konkret: file nyasar
    assert "run1=FAIL" in msgs[2]                 # fakta konkret: pair status


FIX_MD_FULL = """WHAT CHANGED: added __str__ returning the raw value.
WHY: str(choice) now renders the value, which is what the user expects.
FILE: django/db/models/enums.py
CANDIDATE: 1
REPRO: PASS,PASS (frozen repro, fresh container pair)
"""


def test_parse_fix_md_full():
    slots = parse_fix_md(FIX_MD_FULL)
    assert slots["what_changed"].startswith("added")
    assert slots["file"] == "django/db/models/enums.py"
    assert slots["candidate"] == 1
    assert slots["repro"].startswith("PASS,PASS")


def test_parse_fix_md_missing_slots_named():
    with pytest.raises(ValueError, match="WHY"):
        parse_fix_md("WHAT CHANGED: x\n")


def test_compose_fix_md_fills_mechanical_slots_and_drops_model_versions():
    model_part = ("WHAT CHANGED: a\nWHY: b\n"
                  "FILE: fake.py\nCANDIDATE: 9\nREPRO: PASS")
    out = compose_fix_md(model_part, "django/db/models/enums.py", 2,
                         "PASS,PASS (frozen repro, fresh container pair)")
    assert "FILE: django/db/models/enums.py" in out
    assert "CANDIDATE: 2" in out
    assert "fake.py" not in out and "CANDIDATE: 9" not in out
    parse_fix_md(out)  # artefak final wajib lolos parser gate
