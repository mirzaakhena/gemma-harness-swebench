"""Test Lever L#3 (trace-injection): tracer filter + parse pool + injeksi
pesan + subset check candidates ⊆ pool.

Latar (VERDICT L#2, vault R-dev Log): kelas eksplorasi/framing kebal rule
pasif & enumerasi mekanis — file akar tak pernah masuk bidang pandang model.
L#3 memaksa masuk by construction: harness eksekusi repro.py di container
segar di bawah coverage trace, inject himpunan file repo yang TEREKSEKUSI
sebagai kandidat pool, enforce candidates ⊆ pool. Base-world murni, nol gold.
"""
import json

import pytest


# --- tracer in-container: filter file ---------------------------------------

def test_tracer_keep_repo_file():
    from harness.stages.localize_tracer import keep
    assert keep("/testbed/django/db/models/enums.py")


def test_tracer_drop_pipe_workspace():
    # .pipe = workspace model (repro.py, probe) — bukan file repo.
    from harness.stages.localize_tracer import keep
    assert not keep("/testbed/.pipe/repro.py")


def test_tracer_drop_outside_repo_and_non_py():
    from harness.stages.localize_tracer import keep
    assert not keep("/usr/lib/python3.11/enum.py")
    assert not keep("<string>")
    assert not keep("/testbed/README.rst")


def test_tracer_relativize():
    from harness.stages.localize_tracer import relativize
    assert relativize("/testbed/django/apps/config.py") == "django/apps/config.py"


# --- parse output trace run (multi-proses + intersect repo) ----------------

def _raw(pools, repo_files, prefix="REPRO_STATUS: FAIL\n"):
    from harness.stages.localize_trace import REPO_SENTINEL, TRACE_SENTINEL
    lines = [json.dumps(p) for p in pools]
    return (prefix + TRACE_SENTINEL + "\n" + "\n".join(lines) + "\n"
            + REPO_SENTINEL + "\n" + "\n".join(repo_files))


def test_parse_trace_output_unions_processes_and_sorts():
    from harness.stages.localize_trace import parse_trace_output
    pool = parse_trace_output(_raw(
        [["b.py", "a.py"], ["c.py", "b.py"]], ["a.py", "b.py", "c.py"]))
    assert pool == ["a.py", "b.py", "c.py"]


def test_parse_trace_output_intersects_with_repo_files():
    # File scaffold buatan repro (manage.py dkk) tereksekusi di /testbed
    # tapi bukan file repo -> dibuang via git ls-files.
    from harness.stages.localize_trace import parse_trace_output
    pool = parse_trace_output(_raw(
        [["django/x.py", "test_project/manage.py"]], ["django/x.py"]))
    assert pool == ["django/x.py"]


def test_parse_trace_output_missing_sentinel():
    from harness.stages.localize_trace import parse_trace_output
    with pytest.raises(ValueError):
        parse_trace_output("REPRO_STATUS: FAIL\nno pool here")


def test_parse_trace_output_bad_json_line_rejected():
    from harness.stages.localize_trace import REPO_SENTINEL, TRACE_SENTINEL, parse_trace_output
    with pytest.raises(ValueError):
        parse_trace_output(TRACE_SENTINEL + "\n{not json\n"
                           + REPO_SENTINEL + "\nx.py")


def test_parse_trace_output_empty_pool_rejected():
    # Pool kosong = tak ada proses yang menyaksikan file repo (kelas abort
    # 11910 r1) -- tak boleh diinject diam-diam.
    from harness.stages.localize_trace import parse_trace_output
    with pytest.raises(ValueError):
        parse_trace_output(_raw([[]], ["a.py"]))


# --- injeksi pesan user ------------------------------------------------------

def test_format_pool_message_contains_every_file_and_header():
    from harness.stages.localize_trace import (POOL_HEADER,
                                               format_trace_pool_message)
    pool = ["django/db/models/enums.py", "django/db/models/fields/__init__.py"]
    msg = format_trace_pool_message(pool)
    assert POOL_HEADER in msg
    for path in pool:
        assert path in msg


# --- subset check candidates ⊆ pool ------------------------------------------

def test_candidates_pool_error_none_when_subset():
    from harness.stages.localize_trace import candidates_pool_error
    err = candidates_pool_error(
        ["django/db/models/enums.py"],
        {"django/db/models/enums.py", "django/apps/config.py"})
    assert err is None


def test_candidates_pool_error_names_offending_file():
    from harness.stages.localize_trace import candidates_pool_error
    err = candidates_pool_error(
        ["django/db/models/fields/files.py", "django/db/models/enums.py"],
        {"django/db/models/enums.py"})
    assert err is not None
    assert "django/db/models/fields/files.py" in err


def test_candidates_pool_error_tolerates_leading_slash():
    from harness.stages.localize_trace import candidates_pool_error
    assert candidates_pool_error(
        ["/django/db/models/enums.py"], {"django/db/models/enums.py"}) is None


def test_pool_messages_are_english():
    from harness.stages.localize_trace import (candidates_pool_error,
                                               format_trace_pool_message)
    msgs = [
        candidates_pool_error(["x.py"], {"y.py"}),
        format_trace_pool_message(["y.py"]),
    ]
    indonesian_markers = ("Belum", "kamu", "dulu", "berkas", "jalankan")
    for m in msgs:
        assert m
        for word in indonesian_markers:
            assert word not in m, f"pesan ke model masih ber-Indonesia: {m!r}"


# --- drift-guard kontrak -----------------------------------------------------

def test_contract_names_executed_files_rule():
    # Kontrak menyuruh memilih kandidat dari daftar executed-files (data
    # daftarnya per-run, dibawa pesan user pertama oleh driver).
    from pathlib import Path
    import harness.stages.localize_gates as lg
    from harness.stages.localize_trace import POOL_HEADER
    text = (Path(lg.__file__).parent / "localize_prompt.md").read_text(
        encoding="utf-8")
    assert POOL_HEADER in text
