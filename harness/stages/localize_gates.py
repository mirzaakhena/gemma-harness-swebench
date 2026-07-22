"""Gate mekanis stage LOCALIZE — bagian pure-function.

Kontrak: docs/kontrak-output.md §10 (SATU format localize.md) + lever P25:
rentang lines sempit (<= MAX_SPAN), file harus ada, rentang di dalam file.
Cek keberadaan/panjang file dilakukan runner (docker); di sini logika murni.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_SPAN = 200

_SLOT_RES = {
    "chosen": re.compile(r"^chosen:\s*(.+)$", re.MULTILINE),
    "file": re.compile(r"^file:\s*(.+)$", re.MULTILINE),
    "lines": re.compile(r"^lines:\s*(.+)$", re.MULTILINE),
    "what": re.compile(r"^what:\s*(.+)$", re.MULTILINE),
    "why": re.compile(r"^why:\s*(.+)$", re.MULTILINE),
    "evidence": re.compile(r"^evidence:\s*(.+)$", re.MULTILINE),
}
_LINES_RE = re.compile(r"^(\d+)\s*-\s*(\d+)$")


def parse_localize_md(text: str) -> dict:
    """Parse localize.md; ValueError menyebut SEMUA slot yang bermasalah."""
    slots: dict = {}
    missing = []
    for key, rx in _SLOT_RES.items():
        m = rx.search(text)
        if m:
            slots[key] = m.group(1).strip()
        else:
            missing.append(key)
    if missing:
        raise ValueError(f"missing slots in localize.md: {', '.join(missing)}")

    m = _LINES_RE.match(slots["lines"])
    if not m:
        raise ValueError(
            f"slot lines must be N-M (numbers), got: {slots['lines']!r}")
    start, end = int(m.group(1)), int(m.group(2))
    if start > end:
        raise ValueError(f"slot lines reversed: {start}-{end}")
    slots["lines"] = (start, end)
    return slots


@dataclass
class LocalizeResult:
    verdict: str  # pass | fail | syntax-fail
    failures: list[str] = field(default_factory=list)

# Catatan boundary (framing Mirza 2026-07-19): product (harness + model)
# gold-blind total — evaluasi kebenaran vs gold patch hidup TERPISAH di
# lapisan test-system: eval/localize_gold_eval.py.


# --- Lever L#2: enumerasi kandidat mekanis (mandat Mirza 2026-07-19) --------
# Rule pasif L#1 nol efek (11964 1/3->1/3, 11797 0/3->0/3). Kepatuhan
# dipindah ke pagar kode ala bukti-dulu: DONE ditahan sampai candidates.md
# valid (>=2 kandidat, file BERBEDA, evidence + expectation terisi) dan
# file: localize.md anggota daftar kandidat. Semantik "beda lapisan" tidak
# bisa dicek mesin — yang dipaksa adalah bentuknya; slot expectation
# menambatkan tiap kandidat ke ekspektasi eksplisit user (bias framing
# 11964). Cek keberadaan file kandidat di repo = tugas driver (docker).

_CAND_SPLIT_RE = re.compile(r"^CANDIDATE\s+\d+\s*$", re.MULTILINE)
_CAND_SLOT_RES = {
    "file": re.compile(r"^file:\s*(.*)$", re.MULTILINE),
    "evidence": re.compile(r"^evidence:\s*(.*)$", re.MULTILINE),
    "expectation": re.compile(r"^expectation:\s*(.*)$", re.MULTILINE),
}


def parse_candidates_md(text: str) -> list[dict]:
    """Parse candidates.md; ValueError menyebut semua slot bermasalah."""
    blocks = [b for b in _CAND_SPLIT_RE.split(text) if b.strip()]
    if not blocks:
        raise ValueError("no CANDIDATE blocks found")
    cands: list[dict] = []
    problems: list[str] = []
    for i, block in enumerate(blocks, start=1):
        cand: dict = {}
        for key, rx in _CAND_SLOT_RES.items():
            m = rx.search(block)
            val = m.group(1).strip() if m else ""
            if not val:
                problems.append(f"candidate {i}: missing or empty {key}")
            cand[key] = val
        cands.append(cand)
    if problems:
        raise ValueError("; ".join(problems))
    return cands


def candidates_done_error(candidates_text: str | None,
                          localize_file: str | None) -> str | None:
    """Feedback English penahan DONE (None = enumerasi valid).

    Dipanggil driver saat model mendeklarasikan DONE; mekanis murni —
    bentuk, bukan makna."""
    spec = ("submit a ```candidates.md block with at least TWO and at most "
            "THREE candidates from different files, each in this form:\n"
            "CANDIDATE <n>\nfile: <path>\nevidence: <what this code does "
            "that can own the wrong behavior>\nexpectation: <how a change "
            "here directly satisfies what the user explicitly expects in "
            "the issue>")
    if candidates_text is None:
        return f"Not done yet: {spec}"
    try:
        cands = parse_candidates_md(candidates_text)
    except ValueError as e:
        return f"Not done yet: your candidates.md is incomplete ({e}) — {spec}"
    if len(cands) < 2:
        return ("Not done yet: enumerate at least two candidates — " + spec)
    # Pagar shortlist (keputusan Mirza 2026-07-19): kriteria pass = gold ∈
    # kandidat → tanpa batas atas, daftar panjang mengosongkan makna
    # shortlist (anti-gaming).
    if len(cands) > 3:
        return ("Not done yet: keep your shortlist to at most three "
                "candidates — drop the weakest until three remain.")
    files = [c["file"].lstrip("/") for c in cands]
    if len(set(files)) < 2:
        return ("Not done yet: your candidates must come from at least two "
                "different files — a second candidate in the same file does "
                "not widen the search.")
    if localize_file is not None and localize_file.lstrip("/") not in set(files):
        return ("Not done yet: the file in your localize.md must be one of "
                "the candidates you enumerated in candidates.md — either "
                "add it as a candidate with its own evidence and "
                "expectation, or choose among your candidates.")
    return None


# --- Lever N2: audit konsistensi evidence<->file (mandat Mirza 2026-07-22) --
# Bukti 12184: kandidat #1 django/urls/base.py dgn evidence menyebut
# `URLPattern.resolve` — simbol itu TIDAK ada di base.py (adanya di
# resolvers.py, kandidat #2) -> FIX dipenjara 40 turn di file salah.
# Cek mekanis gold-blind: simbol beridiom kode (snake_case/camelCase) yang
# dikutip evidence harus muncul di isi file kandidat; miss ->
# evidence_mismatch + DEMOSI urutan attempt (kandidat TIDAK dihapus — FIX
# mengiterasi seluruh shortlist). File tak terbaca -> JANGAN demosi
# (gagal-aman, prinsip prune). Logika murni di sini; baca file = driver.

# Ambang panjang minimum token yang diaudit: token < 4 huruf (id, get, url)
# terlalu ambigu dgn kata biasa/akronim -> di-skip demi anti-false-positive.
MIN_SYMBOL_LEN = 4
# Token kandidat: identifier ber-titik opsional (URLPattern.resolve).
EVIDENCE_TOKEN_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
# Idiom camelCase/CapsAcronym: transisi lower->UPPER (getResolver,
# ResolverMatch) ATAU run akronim >=2 diikuti ekor lowercase >=2
# (URLPattern; "URLs" — plural Inggris berekor 1 huruf — TIDAK lolos).
MIXED_CASE_RE = re.compile(r"[a-z][A-Z]|[A-Z]{2,}[a-z]{2,}")


def extract_evidence_symbols(evidence: str) -> list[str]:
    """Ekstrak simbol beridiom kode dari teks evidence (urut, unik).

    Yang diaudit hanya token yang TAMPAK seperti identifier kode: mengandung
    underscore, campuran huruf besar-kecil (MIXED_CASE_RE), atau bentuk
    panggilan `nama()`. Kata bahasa Inggris polos sengaja lolos (anti
    false-positive). Token ber-titik dipecah dan tiap komponen dinilai
    sendiri (URLPattern.resolve -> hanya URLPattern yang beridiom)."""
    symbols: list[str] = []
    for m in EVIDENCE_TOKEN_RE.finditer(evidence):
        parts = m.group(0).split(".")
        is_call = evidence[m.end():m.end() + 1] == "("
        for j, part in enumerate(parts):
            if len(part) < MIN_SYMBOL_LEN:
                continue
            shaped = "_" in part or MIXED_CASE_RE.search(part)
            called = is_call and j == len(parts) - 1
            if (shaped or called) and part not in symbols:
                symbols.append(part)
    return symbols


def audit_candidate_evidence(evidence: str, file_text: str | None) -> dict:
    """Audit satu kandidat: simbol evidence vs isi file yang diklaim.

    file_text None = file tak terbaca -> checked False, TIDAK mismatch
    (gagal-aman). Pencocokan substring (bukan word-boundary): lebih longgar
    = lebih aman dari demosi keliru."""
    symbols = extract_evidence_symbols(evidence)
    if file_text is None:
        return {"symbols": symbols, "missing": [], "checked": False,
                "evidence_mismatch": False}
    missing = [s for s in symbols if s not in file_text]
    return {"symbols": symbols, "missing": missing, "checked": True,
            "evidence_mismatch": bool(missing)}


def demote_mismatched_candidates(audits: list[dict]) -> list[int]:
    """Urutan indeks baru: kandidat bersih dulu (urutan asli dipertahankan),
    kandidat evidence_mismatch ke ekor (urutan relatif juga dipertahankan)."""
    clean = [i for i, a in enumerate(audits) if not a["evidence_mismatch"]]
    demoted = [i for i, a in enumerate(audits) if a["evidence_mismatch"]]
    return clean + demoted


def reorder_candidates_text(text: str, order: list[int]) -> str:
    """Susun ulang blok candidates.md sesuai `order` (indeks 0-based lama),
    header dinomori ulang 1..n. Isi blok utuh — format kontrak FIX tetap."""
    blocks = [b for b in _CAND_SPLIT_RE.split(text) if b.strip()]
    out = [f"CANDIDATE {i}\n" + blocks[old].strip("\n")
           for i, old in enumerate(order, start=1)]
    return "\n\n".join(out) + "\n"


def evaluate_localize_gates(md_text: str, file_exists: bool,
                            file_line_count: int | None) -> LocalizeResult:
    try:
        slots = parse_localize_md(md_text)
    except ValueError as e:
        return LocalizeResult(verdict="syntax-fail",
                              failures=[f"localize.md format: {e}"])

    failures: list[str] = []
    start, end = slots["lines"]

    if start < 1:
        failures.append(
            f"lines must start at 1 or later, got {start}-{end}")
    if not file_exists:
        failures.append(f"file does not exist in the repo: {slots['file']}")
    else:
        if end - start + 1 > MAX_SPAN:
            failures.append(
                f"lines range too wide ({end - start + 1} lines > "
                f"{MAX_SPAN}) — a map must point at a site, not a region")
        if file_line_count is not None and end > file_line_count:
            failures.append(
                f"lines {start}-{end} extend beyond the end of file "
                f"({file_line_count} lines)")

    return LocalizeResult(verdict="fail" if failures else "pass",
                          failures=failures)
