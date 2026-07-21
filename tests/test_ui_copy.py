"""Test tombol copy-to-clipboard di tabel utama (permintaan Mirza 2026-07-21).

Tiap baris case punya tombol 📋 yang menyalin string JSON PERSIS
    {"case": "<case_id>", "phase": "<R|L|FV>", "run": "<rN>"}
phase diturunkan dari kampanye/tab aktif: r-dev->R, l-dev->L, f-dev->FV;
run = bagian rerun run_id baris (rerun kosong -> "run": "").
"""
import html
import re

from ui.server import campaign_phase, copy_case_json, page_index


# --- helper murni ------------------------------------------------------------

def test_campaign_phase_mapping():
    assert campaign_phase("r-dev") == "R"
    assert campaign_phase("l-dev") == "L"
    assert campaign_phase("f-dev") == "FV"
    assert campaign_phase("x-camp") == ""


def test_copy_case_json_exact_format():
    # format PERSIS: spasi setelah titik dua & koma, double-quote,
    # urutan case->phase->run
    assert copy_case_json("django__django-11019", "r-dev", "r1") == (
        '{"case": "django__django-11019", "phase": "R", "run": "r1"}')
    assert copy_case_json("sympy__sympy-13971", "l-dev", "r2") == (
        '{"case": "sympy__sympy-13971", "phase": "L", "run": "r2"}')
    assert copy_case_json("django__django-11910", "f-dev", "r3") == (
        '{"case": "django__django-11910", "phase": "FV", "run": "r3"}')


def test_copy_case_json_empty_rerun_fail_soft():
    # run_id tak berformat -> rerun "" -> "run": "" (jangan crash)
    assert copy_case_json("stray-dir", "r-dev", "") == (
        '{"case": "stray-dir", "phase": "R", "run": ""}')


# --- render tombol di page_index --------------------------------------------

def _data_copy_values(out: str) -> list[str]:
    """Ambil semua nilai atribut data-copy (sudah di-unescape) dari HTML."""
    return [html.unescape(m) for m in re.findall(r'data-copy="([^"]*)"', out)]


def _mk_dir(tmp_path, campaign, case):
    (tmp_path / campaign / f"{campaign}--{case}--r1").mkdir(parents=True)


def test_page_index_copy_button_phase_r(tmp_path):
    _mk_dir(tmp_path, "r-dev", "django__django-11019")
    out = page_index(tmp_path, tab="r-dev")
    assert "class='copybtn'" in out
    assert "onclick='copyCaseJSON(this)'" in out
    assert '{"case": "django__django-11019", "phase": "R", "run": "r1"}' in \
        _data_copy_values(out)


def test_page_index_copy_button_phase_l(tmp_path):
    _mk_dir(tmp_path, "l-dev", "sympy__sympy-13971")
    out = page_index(tmp_path, tab="l-dev")
    assert '{"case": "sympy__sympy-13971", "phase": "L", "run": "r1"}' in \
        _data_copy_values(out)


def test_page_index_copy_button_phase_fv(tmp_path):
    _mk_dir(tmp_path, "f-dev", "django__django-11910")
    out = page_index(tmp_path, tab="f-dev")
    assert '{"case": "django__django-11910", "phase": "FV", "run": "r1"}' in \
        _data_copy_values(out)


def test_page_index_copy_button_carries_row_rerun(tmp_path):
    # run = bagian rerun run_id BARIS itu (bukan selalu r1)
    (tmp_path / "r-dev" / "r-dev--django__django-11019--r7").mkdir(parents=True)
    out = page_index(tmp_path, tab="r-dev")
    assert '{"case": "django__django-11019", "phase": "R", "run": "r7"}' in \
        _data_copy_values(out)


def test_page_index_copy_button_one_per_case_row(tmp_path):
    # dua case di r-dev -> dua tombol copy dgn phase R + run yang benar
    _mk_dir(tmp_path, "r-dev", "django__django-11019")
    _mk_dir(tmp_path, "r-dev", "django__django-12308")
    out = page_index(tmp_path, tab="r-dev")
    vals = _data_copy_values(out)
    assert '{"case": "django__django-11019", "phase": "R", "run": "r1"}' in vals
    assert '{"case": "django__django-12308", "phase": "R", "run": "r1"}' in vals
    assert out.count("class='copybtn'") == 2


def test_copy_json_attribute_is_quote_escaped(tmp_path):
    # JSON mengandung double-quote -> WAJIB di-escape sbg &quot; di atribut
    _mk_dir(tmp_path, "r-dev", "django__django-11019")
    out = page_index(tmp_path, tab="r-dev")
    assert "&quot;case&quot;" in out
    # JS fallback + secure-context handler harus ada di halaman
    assert "navigator.clipboard" in out
    assert "execCommand('copy')" in out
