"""Drift-guard kontrak fix_prompt.md — English, ultra-slim, scope positif
(higiene prinsip-pengembangan §4b: tanpa narasi mekanisme enforcement,
tanpa larangan yang menunjuk target)."""
from pathlib import Path

CONTRACT = (Path(__file__).resolve().parents[1] / "harness" / "stages"
            / "fix_prompt.md").read_text(encoding="utf-8")


def test_contract_is_english():
    for word in ("Belum", "kamu", "dulu", "serahkan", "jalankan", "berkas"):
        assert word not in CONTRACT, f"kontrak masih ber-Indonesia: {word}"


def test_contract_names_required_tokens():
    assert "REPRO_STATUS: PASS" in CONTRACT
    assert "REPRO_STATUS: FAIL" in CONTRACT
    assert "WHAT CHANGED:" in CONTRACT
    assert "WHY:" in CONTRACT
    assert "DONE" in CONTRACT
    assert "/testbed/.pipe/repro.py" in CONTRACT


def test_contract_positive_scope_no_enforcement_narration():
    low = CONTRACT.lower()
    for phrase in ("do not", "don't", "forbidden", "must not",
                   "harness", "gate", "will be rejected", "reject"):
        assert phrase not in low, f"narasi larangan/enforcement: {phrase!r}"
    assert "edit site" in low  # scope positif


def test_contract_interpretive_slots_only():
    # Slot mekanis (FILE/CANDIDATE/REPRO) diisi harness — kontrak tidak
    # menyuruh model menulisnya (pola compose_repro_md).
    assert "FILE:" not in CONTRACT
    assert "CANDIDATE:" not in CONTRACT
