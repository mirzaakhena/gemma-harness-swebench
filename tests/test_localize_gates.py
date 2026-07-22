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


def test_gate_lines_zero_start_rejected():
    # Lever L-a: rentang wajib >=1 — baris 0 tidak ada; definisi tunggal
    # gate <-> driver (driver DONE-check me-mirror evaluate_localize_gates).
    md = MD_OK.replace("lines: 105-130", "lines: 0-130")
    r = evaluate_localize_gates(md, file_exists=True, file_line_count=640)
    assert r.verdict == "fail"
    assert any("start at 1" in f for f in r.failures)


def test_gate_malformed_md_is_syntax_fail():
    r = evaluate_localize_gates("chosen: 1\n", file_exists=True, file_line_count=100)
    assert r.verdict == "syntax-fail"


# --- Lever L#2: enumerasi kandidat mekanis (mandat Mirza 2026-07-19) --------
# Rule pasif L#1 nol efek (11964 1/3->1/3, 11797 0/3->0/3). Kepatuhan
# dipindah ke pagar kode: candidates.md wajib (>=2 kandidat, file berbeda,
# evidence + expectation non-kosong), file: localize.md harus anggota daftar.

CANDS_OK = """CANDIDATE 1
file: django/db/models/lookups.py
evidence: Exact.process_rhs uses the target field pk when rhs is a values() queryset.
expectation: str(b.query) would show GROUP BY on email, matching what the user expects.

CANDIDATE 2
file: django/db/models/sql/query.py
evidence: get_group_by builds the GROUP BY clause from the select columns.
expectation: the rendered subquery keeps the email grouping the user asked about.
"""


def test_parse_candidates_md_ok():
    from harness.stages.localize_gates import parse_candidates_md
    cands = parse_candidates_md(CANDS_OK)
    assert len(cands) == 2
    assert cands[0]["file"] == "django/db/models/lookups.py"
    assert cands[1]["file"] == "django/db/models/sql/query.py"
    assert cands[0]["evidence"].startswith("Exact.process_rhs")
    assert cands[0]["expectation"]


def test_candidates_done_error_none_when_valid_and_member():
    from harness.stages.localize_gates import candidates_done_error
    assert candidates_done_error(
        CANDS_OK, "django/db/models/lookups.py") is None


def test_candidates_done_error_missing_block():
    from harness.stages.localize_gates import candidates_done_error
    err = candidates_done_error(None, "x.py")
    assert err is not None and "candidates.md" in err


def test_candidates_done_error_needs_two_distinct_files():
    from harness.stages.localize_gates import candidates_done_error
    one = CANDS_OK.split("\nCANDIDATE 2")[0]
    err = candidates_done_error(one, "django/db/models/lookups.py")
    assert err is not None and "two" in err.lower()
    dup = CANDS_OK.replace("django/db/models/sql/query.py",
                           "django/db/models/lookups.py")
    err2 = candidates_done_error(dup, "django/db/models/lookups.py")
    assert err2 is not None and "different files" in err2


def test_candidates_done_error_requires_slots():
    from harness.stages.localize_gates import candidates_done_error
    no_exp = CANDS_OK.replace(
        "expectation: str(b.query) would show GROUP BY on email, matching what the user expects.",
        "expectation:")
    err = candidates_done_error(no_exp, "django/db/models/lookups.py")
    assert err is not None and "expectation" in err


def test_candidates_done_error_localize_file_must_be_member():
    from harness.stages.localize_gates import candidates_done_error
    err = candidates_done_error(CANDS_OK, "django/db/models/enums.py")
    assert err is not None and "one of the candidates" in err


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


# --- Pagar shortlist: kandidat 2-3 file (keputusan Mirza 2026-07-19) --------
# Kriteria pass jadi "gold ∈ kandidat" — tanpa batas atas, daftar panjang
# mengosongkan makna shortlist (anti-gaming).

CANDS_FOUR = "\n".join(
    f"CANDIDATE {i}\nfile: pkg/mod{i}.py\nevidence: does thing {i} that can own it.\n"
    f"expectation: change here satisfies the user's explicit expectation."
    for i in range(1, 5))


def test_candidates_done_error_rejects_more_than_three():
    from harness.stages.localize_gates import candidates_done_error
    err = candidates_done_error(CANDS_FOUR, "pkg/mod1.py")
    assert err is not None and "three" in err.lower()


def test_candidates_done_error_accepts_three():
    from harness.stages.localize_gates import candidates_done_error
    three = CANDS_FOUR.split("\nCANDIDATE 4")[0]
    assert candidates_done_error(three, "pkg/mod2.py") is None


def test_contract_names_shortlist_bounds():
    text = _contract_text()
    assert "at most THREE" in text


# --- Lever N2: audit konsistensi evidence<->file (mandat Mirza 2026-07-22) --
# Bukti 12184: kandidat #1 django/urls/base.py dgn evidence menyebut
# URLPattern.resolve — simbol itu tidak ada di base.py (adanya di
# resolvers.py, kandidat #2) -> FIX dipenjara 40 turn di file salah.
# Cek mekanis gold-blind: simbol beridiom kode di evidence harus muncul di
# isi file kandidat; miss -> evidence_mismatch + demosi urutan (bukan hapus).


def test_extract_symbols_camel_and_snake():
    from harness.stages.localize_gates import extract_evidence_symbols
    syms = extract_evidence_symbols(
        "URLPattern.resolve walks url_patterns before the include is applied.")
    assert "URLPattern" in syms
    assert "url_patterns" in syms
    # kata Inggris polos & komponen dotted tanpa idiom kode tidak diaudit
    assert "resolve" not in syms
    assert "before" not in syms and "walks" not in syms


def test_extract_symbols_call_form_qualifies():
    from harness.stages.localize_gates import extract_evidence_symbols
    syms = extract_evidence_symbols(
        "the resolve() helper rebuilds the match before returning.")
    assert syms == ["resolve"]


def test_extract_symbols_skips_short_and_acronym_only():
    from harness.stages.localize_gates import extract_evidence_symbols
    # id() < MIN_SYMBOL_LEN; URL tanpa ekor lowercase; URLs ekor 1 huruf
    # (plural bahasa Inggris, bukan identifier) — semuanya di-skip.
    assert extract_evidence_symbols(
        "the id() call maps a URL and the URLs are rewritten") == []


def test_extract_symbols_dedup_preserves_order():
    from harness.stages.localize_gates import extract_evidence_symbols
    syms = extract_evidence_symbols(
        "get_group_by feeds get_group_by again via GroupByHelper")
    assert syms == ["get_group_by", "GroupByHelper"]


def test_audit_mismatch_when_symbol_absent_from_file():
    from harness.stages.localize_gates import audit_candidate_evidence
    # Reproduksi 12184: evidence menyebut URLPattern, file base.py tidak
    # memuat simbol itu.
    a = audit_candidate_evidence(
        "URLPattern.resolve strips the prefix before matching.",
        "def resolve(path, urlconf=None):\n    return get_resolver()\n")
    assert a["checked"] is True
    assert a["evidence_mismatch"] is True
    assert a["missing"] == ["URLPattern"]


def test_audit_pass_when_symbols_present():
    from harness.stages.localize_gates import audit_candidate_evidence
    a = audit_candidate_evidence(
        "URLPattern.resolve strips the prefix.",
        "class URLPattern:\n    def resolve(self, path):\n        pass\n")
    assert a["evidence_mismatch"] is False and a["missing"] == []


def test_audit_unreadable_file_fails_safe():
    from harness.stages.localize_gates import audit_candidate_evidence
    # File tak terbaca -> JANGAN demosi (gagal-aman, prinsip prune).
    a = audit_candidate_evidence("URLPattern.resolve does it.", None)
    assert a["checked"] is False
    assert a["evidence_mismatch"] is False


def test_audit_prose_only_evidence_never_mismatch():
    from harness.stages.localize_gates import audit_candidate_evidence
    a = audit_candidate_evidence(
        "this branch renders the wrong string for the user.", "x = 1\n")
    assert a["symbols"] == [] and a["evidence_mismatch"] is False


def test_demote_moves_mismatch_to_tail_keeps_relative_order():
    from harness.stages.localize_gates import demote_mismatched_candidates
    audits = [{"evidence_mismatch": True}, {"evidence_mismatch": False},
              {"evidence_mismatch": True}, {"evidence_mismatch": False}]
    assert demote_mismatched_candidates(audits) == [1, 3, 0, 2]


def test_demote_identity_when_clean():
    from harness.stages.localize_gates import demote_mismatched_candidates
    audits = [{"evidence_mismatch": False}, {"evidence_mismatch": False}]
    assert demote_mismatched_candidates(audits) == [0, 1]


def test_reorder_candidates_text_renumbers_and_reparses():
    from harness.stages.localize_gates import (parse_candidates_md,
                                               reorder_candidates_text)
    out = reorder_candidates_text(CANDS_OK, [1, 0])
    cands = parse_candidates_md(out)
    assert [c["file"] for c in cands] == [
        "django/db/models/sql/query.py", "django/db/models/lookups.py"]
    # header dinomori ulang urut 1..n — format kontrak FIX tidak berubah
    assert "CANDIDATE 1\n" in out and "CANDIDATE 2\n" in out
    assert cands[0]["evidence"].startswith("get_group_by")
    assert cands[1]["expectation"]
