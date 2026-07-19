"""Test RULE_CATALOG-R — injeksi aturan diambil VERBATIM dari kontrak.

Keputusan Mirza 2026-07-18 malam: katalognya adalah system prompt itu
sendiri — aturan ber-ID, injeksi mengutip kalimat kontrak apa adanya
(satu sumber kebenaran), detector memilih aturan saat sinyalnya menyala.
Drift-guard: setiap quote WAJIB substring (ternormalisasi spasi) dari
reproduce_prompt.md — kontrak berubah tanpa katalog ikut → test merah.
"""
import re
from pathlib import Path

import pytest

from harness.stages import rule_catalog


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


CONTRACT = (Path(rule_catalog.__file__).parent / "reproduce_prompt.md").read_text(
    encoding="utf-8")


def test_every_rule_quote_is_verbatim_from_contract():
    norm_contract = _norm(CONTRACT)
    for rule_id, quote in rule_catalog.RULES.items():
        assert _norm(quote) in norm_contract, (
            f"rule {rule_id!r} drift: quote tidak ditemukan di kontrak")


def test_expected_rule_ids_present():
    for rid in ("self-contained", "repeatable", "early-draft",
                "source-pass-side", "crash-repair", "positive-control",
                "settle-before-trigger", "app-runtime",
                "predicate-from-witnessed-output", "scope-minimal-predicate",
                "observable-behavior-change", "robust-scaffold"):
        assert rid in rule_catalog.RULES


def test_app_runtime_rule_stays_in_core():
    # Keputusan Mirza 2026-07-19 (pasca-r32): mekanika start/settle/echo
    # dipindah ke modul pipe_runtime; keberadaannya WAJIB ditegaskan di
    # prompt (CORE) supaya Gemma diarahkan memakainya.
    core = rule_catalog.core_contract()
    assert "pipe_runtime" in core
    assert "wait_ready" in core
    # Kelas r35: model membungkus wait_* dengan try/except seolah raise —
    # padahal return bool; semantiknya WAJIB tegas di kontrak.
    assert "never raise" in core
    assert "check their return value" in core


def test_settle_rule_stays_in_core():
    # Keputusan Mirza 2026-07-19: kelas race signal-less (5 kejadian) tidak
    # bisa injeksi-only — kalimat kompaknya WAJIB tampil di CORE.
    core = rule_catalog.core_contract()
    assert "let\nthe mechanism settle first" in core.replace("\r\n", "\n") or \
           "mechanism settle first" in core


def test_inject_quotes_the_rule():
    msg = rule_catalog.inject("self-contained")
    assert "contract" in msg.lower()
    assert _norm(rule_catalog.RULES["self-contained"]) in _norm(msg)


def test_inject_unknown_id_raises():
    with pytest.raises(KeyError):
        rule_catalog.inject("nonexistent-rule")


# --- dua-tier (keputusan Mirza 2026-07-19 dinihari): CORE vs DETAIL ---------

def test_core_contract_has_no_marker_comments():
    core = rule_catalog.core_contract()
    assert "<!--" not in core


def test_core_contract_drops_detail_rules():
    core = rule_catalog.core_contract()
    assert "FAITHFUL SETUP" not in core
    assert "Source the PASS side" not in core


def test_positive_control_rule_stays_in_core():
    # Keputusan Mirza 2026-07-19 (setelah r30): kelas pass-fidelity/setup-rusak
    # (r29+r30, `--noreload=false`) signal-less di sisi base — per kriteria
    # "aturan signal-less tidak boleh injeksi-only", versi kompak
    # positive-control WAJIB tampil di CORE.
    core = rule_catalog.core_contract()
    assert "positive control" in core
    assert "diagnostic" in core


def test_core_contract_keeps_core_rules_and_skeleton():
    core = rule_catalog.core_contract()
    assert "REPRO_STATUS: FAIL" in core
    assert "SYMPTOM:" in core
    assert "Definition of done" in core


def test_ultra_slim_self_contained_and_repeatable_are_detail_only():
    # Eksperimen ULTRA-SLIM (antrian pasca-stabil, disetujui Mirza):
    # keduanya kini di-enforce FISIKA (repro selalu-fresh + pre-check pair),
    # jadi turun ke detail-only — CORE tinggal tujuan+output+protokol+
    # invarian signal-less. Mulai r42.
    core = rule_catalog.core_contract()
    assert "inside the script itself" not in core
    assert "identical output" not in core


def test_core_contract_promote_renders_selected_detail_blocks():
    # A/B test 11999 (keputusan Mirza): varian "full" merender kembali
    # self-contained & repeatable tanpa bolak-balik commit kontrak.
    core = rule_catalog.core_contract(promote=("self-contained",
                                               "repeatable"))
    assert "inside the script itself" in core
    assert "identical output" in core
    assert "FAITHFUL SETUP" not in core   # detail lain tetap tersembunyi


def test_core_contract_default_has_no_promoted_details():
    assert "inside the script itself" not in rule_catalog.core_contract()


def test_predicate_from_witnessed_output_rule_stays_in_core():
    # Paket Predikat (keputusan Mirza 2026-07-19, pasca-survey 5 case):
    # kelas predikat-literal-rapuh (11797 r2+r3) — string SQL ditebak alih-
    # alih diturunkan dari output yang script print sendiri; base-FAIL via
    # fallback branch = signal-less di sisi base → wajib CORE.
    core = _norm(rule_catalog.core_contract())
    assert "observed form" in core
    assert "align the predicate" in core


def test_scope_minimal_predicate_rule_stays_in_core():
    # Paket Predikat (keputusan Mirza 2026-07-19, pasca-survey 5 case):
    # kelas over-testing gold-unsatisfiable (13220 3× deterministik) —
    # predikat menuntut lebih dari klaim eksplisit issue; signal-less di
    # base → wajib CORE.
    core = _norm(rule_catalog.core_contract())
    assert "narrowest concrete claim" in core
    assert "stay out of the predicate" in core


def test_observable_behavior_change_rule_stays_in_core():
    # Lever R-a (11905 0/3): issue kelas "prevent/reject X" — model menuntut
    # exception spesifik (TypeError/ValueError) padahal perilaku benar bisa
    # berupa deprecation warning -> predikat tak pernah flip. Signal-less
    # di base (tak ada sinyal mekanis pemicu injeksi) -> wajib rule CORE.
    core = _norm(rule_catalog.core_contract())
    assert "no longer silently accepted" in core
    assert "any type" in core
    assert "warning" in core
    # marker rule ter-unwrap, tidak bocor ke model
    assert "observable-behavior-change" not in core


def test_observable_behavior_change_rule_is_injectable():
    msg = rule_catalog.inject("observable-behavior-change")
    assert _norm(rule_catalog.RULES["observable-behavior-change"]) in _norm(msg)


def test_robust_scaffold_rule_stays_in_core():
    # Lever R-b (13768 0/3): scaffold minimal (konfigurasi framework tak
    # lengkap + logging default terpasang) CRASH di dunia patched saat fix
    # menambah jalur baru (logging -> error-reporting -> akses setting yang
    # tak ada) -> token REPRO_STATUS hilang. Signal-less di base -> wajib
    # CORE.
    core = _norm(rule_catalog.core_contract())
    assert "every setting" in core
    assert "root of the logging hierarchy" in core
    # marker rule ter-unwrap, tidak bocor ke model
    assert "robust-scaffold" not in core


def test_robust_scaffold_rule_is_case_agnostic():
    # Rumusan generik — tanpa menyebut framework/setting spesifik kasusnya.
    text = rule_catalog.RULES["robust-scaffold"]
    assert "Django" not in text
    assert "SECRET_KEY" not in text


def test_robust_scaffold_rule_is_injectable():
    msg = rule_catalog.inject("robust-scaffold")
    assert _norm(rule_catalog.RULES["robust-scaffold"]) in _norm(msg)


def test_detail_rules_are_extracted_for_injection():
    for rid in ("faithful-setup", "pass-fidelity", "source-pass-side",
                "crash-repair", "positive-control", "self-contained",
                "repeatable"):
        assert rid in rule_catalog.RULES
        assert len(rule_catalog.RULES[rid]) > 50
