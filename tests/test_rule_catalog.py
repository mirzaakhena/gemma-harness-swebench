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
                "source-pass-side", "crash-repair", "positive-control"):
        assert rid in rule_catalog.RULES


def test_inject_quotes_the_rule():
    msg = rule_catalog.inject("self-contained")
    assert "contract" in msg.lower()
    assert _norm(rule_catalog.RULES["self-contained"]) in _norm(msg)


def test_inject_unknown_id_raises():
    with pytest.raises(KeyError):
        rule_catalog.inject("nonexistent-rule")
