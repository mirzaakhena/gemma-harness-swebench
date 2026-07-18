"""RULE_CATALOG-R — injeksi aturan kontrak saat sinyal mekanis menyala.

Keputusan Mirza 2026-07-18/19 (Telegram): formalisasi pola living-checklist
P24 harness lama, dengan dua prinsip darinya: (1) KATALOG = SYSTEM PROMPT
ITU SENDIRI — aturan diambil verbatim dari reproduce_prompt.md, satu sumber
kebenaran; (2) system prompt DIRAMPINGKAN — "jangan bebani Gemma dengan hal
yang belum tentu dia hasilkan": blok DETAIL tidak dirender ke model dan
hanya muncul via injeksi saat sinyalnya menyala.

Marker di reproduce_prompt.md:
  <!-- rule:id -->...<!-- /rule -->     tampil di CORE + bisa di-inject
  <!-- detail:id -->...<!-- /detail --> TIDAK dirender; injeksi-only

Detector (sinyal → rule_id) hidup di titik sinyal driver:
  - repro run crash (exit != 0, tanpa REPRO_STATUS)      → crash-repair
  - FAIL sudah disaksikan tapi repro.md belum disetor    → early-draft
  - PASS_OBSERVABLE tak ditemukan di source/script       → source-pass-side
  - fresh-sandbox run tanpa REPRO_STATUS: FAIL           → self-contained
  - dua fresh-sandbox run tidak konsisten                → repeatable
    (+ positive-control bila output menyebut control)
Drift-guard: tests/test_rule_catalog.py.
"""
from __future__ import annotations

import re
from pathlib import Path

_CONTRACT_PATH = Path(__file__).with_name("reproduce_prompt.md")

_RULE_RE = re.compile(r"<!--\s*rule:([a-z-]+)\s*-->(.*?)<!--\s*/rule\s*-->",
                      re.DOTALL)
_DETAIL_RE = re.compile(r"<!--\s*detail:([a-z-]+)\s*-->(.*?)<!--\s*/detail\s*-->",
                        re.DOTALL)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _contract_text() -> str:
    return _CONTRACT_PATH.read_text(encoding="utf-8")


def _load_rules() -> dict[str, str]:
    text = _contract_text()
    rules: dict[str, str] = {}
    for rx in (_RULE_RE, _DETAIL_RE):
        for m in rx.finditer(text):
            rules[m.group(1)] = m.group(2).strip()
    return rules


RULES: dict[str, str] = _load_rules()


def core_contract() -> str:
    """Kontrak yang DIRENDER ke model: blok detail dibuang, marker rule
    di-unwrap, komentar lain dihapus, deret baris kosong dirapikan."""
    text = _contract_text()
    text = _DETAIL_RE.sub("", text)
    text = _RULE_RE.sub(lambda m: m.group(2), text)
    text = _COMMENT_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def inject(rule_id: str) -> str:
    """Pesan injeksi English: kutipan verbatim (ternormalisasi spasi) dari
    kontrak, diberi bingkai singkat tanpa narasi mekanisme."""
    quote = RULES[rule_id]  # KeyError utk id tak dikenal — bug pemanggil
    return ("This contract rule applies to your current situation:\n"
            f"> {_norm(quote)}")
