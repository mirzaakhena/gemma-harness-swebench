"""RULE_CATALOG-R — injeksi aturan kontrak saat sinyal mekanis menyala.

Keputusan Mirza 2026-07-18 malam (Telegram): formalisasi pola
living-checklist P24 harness lama (architecture.md:30 — "model kecil
mengabaikan prompt sekali-tembak; suntik ulang tepat saat sinyalnya
menyala"), dengan prinsip tambahan darinya: KATALOG = SYSTEM PROMPT ITU
SENDIRI. Setiap aturan ber-ID mengutip kalimat reproduce_prompt.md
verbatim — satu sumber kebenaran, tanpa parafrase yang bisa drift.
Drift-guard: tests/test_rule_catalog.py menolak quote yang tidak lagi
ada di kontrak.

Detector (sinyal → rule_id) hidup di titik sinyal driver:
  - repro run crash (exit != 0, tanpa REPRO_STATUS)      → crash-repair
  - FAIL sudah disaksikan tapi repro.md belum disetor    → early-draft
  - PASS_OBSERVABLE tak ditemukan di source/script       → source-pass-side
  - fresh-sandbox run tanpa REPRO_STATUS: FAIL           → self-contained
  - dua fresh-sandbox run tidak konsisten                → repeatable
    (+ positive-control bila output menyebut control)
"""
from __future__ import annotations

import re

# Quote diambil verbatim dari reproduce_prompt.md (spasi/pemenggalan baris
# dinormalisasi saat render — pembandingan drift juga ternormalisasi).
RULES: dict[str, str] = {
    "self-contained": (
        "It runs with `python /testbed/.pipe/repro.py` and nothing else: create\n"
        "     any settings, app, or fixtures it needs inside the script itself."),
    "repeatable": (
        "It is repeatable: running it twice produces identical output; clean up\n"
        "     any state it creates."),
    "early-draft": (
        "Submit an early draft of `repro.md` as soon as your first probe succeeds, and\n"
        "refine it as you learn — an early rough draft beats a polished one that never\n"
        "gets submitted."),
    "source-pass-side": (
        "derive the exact expected\n"
        "     observable — the precise log message, attribute, or value — by READING\n"
        "     the repository source that produces it, and quote it exactly."),
    "crash-repair": (
        "If your scenario crashes for a reason that is not the reported symptom,\n"
        "     repair the script — a crash counts as FAIL only when the crash IS the\n"
        "     symptom the user reports."),
    "positive-control": (
        "When your predicate is \"event X never happens\", prove the absence is\n"
        "     meaningful with a positive control: first make the SAME detection\n"
        "     machinery catch the event triggered through a neighboring path that\n"
        "     already works at the base commit, then trigger it through the path\n"
        "     the issue complains about."),
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def inject(rule_id: str) -> str:
    """Pesan injeksi English: kutipan verbatim (ternormalisasi spasi) dari
    kontrak, diberi bingkai singkat tanpa narasi mekanisme."""
    quote = RULES[rule_id]  # KeyError utk id tak dikenal — bug pemanggil
    return ("This contract rule applies to your current situation:\n"
            f"> {_norm(quote)}")
