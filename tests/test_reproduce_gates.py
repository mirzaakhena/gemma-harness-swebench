"""Test gate mekanis stage REPRODUCE (bagian pure-function).

Kontrak: docs/kontrak-output.md §9 + harness/stages/reproduce_prompt.md.
Eksekusi docker (self-contained re-run) hidup di runner terpisah; di sini
hanya logika murni yang dites.
"""
import pytest

from harness.stages.reproduce_gates import (
    GateResult,
    evaluate_gates,
    parse_repro_md,
    parse_repro_status,
)


# --- parse_repro_status ----------------------------------------------------

def test_parse_status_fail():
    assert parse_repro_status("blah\nREPRO_STATUS: FAIL\n") == "FAIL"


def test_parse_status_pass():
    assert parse_repro_status("ok\nREPRO_STATUS: PASS") == "PASS"


def test_parse_status_takes_last_occurrence():
    out = "REPRO_STATUS: PASS\nsetup ulang...\nREPRO_STATUS: FAIL\n"
    assert parse_repro_status(out) == "FAIL"


def test_parse_status_absent_returns_none():
    assert parse_repro_status("tidak ada token di sini") is None


def test_parse_status_must_be_exact_token():
    assert parse_repro_status("REPRO_STATUS: MAYBE") is None


# --- parse_repro_md --------------------------------------------------------

REPRO_MD_OK = """SYMPTOM: autoreload tidak memantau manage.py
TRIGGER: jalankan runserver via python manage.py
EXPECTED vs ACTUAL:
EXPECTED: manage.py ikut dipantau autoreloader
ACTUAL: perubahan manage.py tidak memicu reload
REPRO COMMAND: python /testbed/.pipe/repro.py
CONFIRMED-AT-BASE: yes
"""


def test_parse_repro_md_ok():
    slots = parse_repro_md(REPRO_MD_OK)
    assert slots["symptom"].startswith("autoreload")
    assert slots["expected"].startswith("manage.py")
    assert slots["actual"].startswith("perubahan")
    assert slots["repro_command"] == "python /testbed/.pipe/repro.py"
    assert slots["confirmed_at_base"] == "yes"


def test_parse_repro_md_missing_slot_raises():
    with pytest.raises(ValueError, match="CONFIRMED-AT-BASE"):
        parse_repro_md("SYMPTOM: x\nTRIGGER: y\n")


# --- evaluate_gates --------------------------------------------------------

def _ok_kwargs(**over):
    kw = dict(
        repro_md_text=REPRO_MD_OK,
        fresh_run1_output="setup\nREPRO_STATUS: FAIL\n",
        fresh_run1_exit=1,
        fresh_run2_output="setup\nREPRO_STATUS: FAIL\n",
        fresh_run2_exit=1,
        scaffolding_error_markers=("ModuleNotFoundError", "ImproperlyConfigured"),
    )
    kw.update(over)
    return kw


def test_all_gates_pass():
    r = evaluate_gates(**_ok_kwargs())
    assert isinstance(r, GateResult)
    assert r.verdict == "pass"
    assert r.failures == []


def test_gate_anti_vacuous_pass_at_base_rejected():
    r = evaluate_gates(**_ok_kwargs(
        fresh_run1_output="REPRO_STATUS: PASS\n", fresh_run1_exit=0,
        fresh_run2_output="REPRO_STATUS: PASS\n", fresh_run2_exit=0,
    ))
    assert r.verdict == "fail"
    assert any("vacuous" in f for f in r.failures)


def test_gate_status_token_missing_is_syntax_fail():
    r = evaluate_gates(**_ok_kwargs(
        fresh_run1_output="tanpa token\n",
        fresh_run2_output="tanpa token\n",
    ))
    assert r.verdict == "syntax-fail"


def test_gate_scaffolding_error_rejected():
    r = evaluate_gates(**_ok_kwargs(
        fresh_run1_output="Traceback...\nModuleNotFoundError: No module named 'repro'\n",
        fresh_run2_output="Traceback...\nModuleNotFoundError: No module named 'repro'\n",
    ))
    assert r.verdict == "fail"
    assert any("self-contained" in f for f in r.failures)


def test_gate_idempotent_mismatch_rejected():
    r = evaluate_gates(**_ok_kwargs(
        fresh_run2_output="setup\nREPRO_STATUS: PASS\n",
    ))
    assert r.verdict == "fail"
    assert any("idempoten" in f for f in r.failures)


def test_gate_confirmed_at_base_no_rejected():
    md = REPRO_MD_OK.replace("CONFIRMED-AT-BASE: yes", "CONFIRMED-AT-BASE: no")
    r = evaluate_gates(**_ok_kwargs(repro_md_text=md))
    assert r.verdict == "fail"
    assert any("CONFIRMED-AT-BASE" in f for f in r.failures)


def test_gate_malformed_repro_md_is_syntax_fail():
    r = evaluate_gates(**_ok_kwargs(repro_md_text="SYMPTOM: saja\n"))
    assert r.verdict == "syntax-fail"


# --- compose_repro_md (slot mekanis diisi harness, bukan model) -------------

MODEL_PART = """SYMPTOM: autoreload does not watch manage.py
TRIGGER: run the server via python manage.py
EXPECTED vs ACTUAL:
EXPECTED: manage.py is watched by the autoreloader
ACTUAL: edits to manage.py never trigger a reload
"""


def test_compose_appends_mechanical_slots_confirmed_yes():
    from harness.stages.reproduce_gates import compose_repro_md
    full = compose_repro_md(MODEL_PART, observed_fail=True)
    slots = parse_repro_md(full)
    assert slots["repro_command"] == "python /testbed/.pipe/repro.py"
    assert slots["confirmed_at_base"] == "yes"
    assert slots["symptom"].startswith("autoreload")


def test_compose_confirmed_no_when_fail_never_observed():
    from harness.stages.reproduce_gates import compose_repro_md
    full = compose_repro_md(MODEL_PART, observed_fail=False)
    assert parse_repro_md(full)["confirmed_at_base"] == "no"


def test_compose_replaces_model_written_mechanical_slots():
    from harness.stages.reproduce_gates import compose_repro_md
    sneaky = MODEL_PART + "REPRO COMMAND: python other.py\nCONFIRMED-AT-BASE: yes\n"
    full = compose_repro_md(sneaky, observed_fail=False)
    slots = parse_repro_md(full)
    assert slots["repro_command"] == "python /testbed/.pipe/repro.py"
    assert slots["confirmed_at_base"] == "no"
    assert full.count("CONFIRMED-AT-BASE:") == 1
    assert full.count("REPRO COMMAND:") == 1
