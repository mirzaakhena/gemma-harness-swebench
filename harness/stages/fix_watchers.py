"""Watcher loop FIX — logika keputusan MURNI (tanpa docker/HTTP/IO).

Lever G2 (docs/rekomendasi-lever-dari-taksonomi.md §7, keputusan Mirza
2026-07-22), habitat: loop turn run_fix_gemma. Pola no_progress.py (R5):
fungsi murni di modul sendiri supaya unit-testable tanpa endpoint/container.

N1 — watcher reply-hash. Di temp 0.0 konteks feedback konstan menghasilkan
reply konstan (bukti: 12184 r12 — 32 reply md5-identik t9–t40; 15388 r9 —
30×+6×); watcher no_progress hanya hidup di REPRODUCE. Di FIX jalan
keluarnya BUKAN injeksi konten ke konteks model, melainkan AKHIRI attempt
dini — rotasi kandidat yang sudah ada mengambil alih (mekanisme yang
menyelamatkan 12184 r9). md5(reply_N)==md5(reply_N-1) 2× berturut-turut
= 3 reply identik beruntun (KH-21: byte-identity, TANPA normalisasi).

N1b — deteksi periode-2 (promosi sweep 2026-07-23, katalog): siklus
A-B-A-B LOLOS semua trigger "3-identik-beruntun" (spesimen penentu
f-dev 12184-r14: 26 hit t11–t40 di bawah N1 aktif; 19 run periode-2
murni di korpus). Hit = md5(reply_N)==md5(reply_N-2); 3 hit beruntun
(= A-B-A-B-A, 5 reply) -> akhiri attempt, label `reply-hash-p2`.
Content-blind murni — menyerang kelas taksonomi, bukan semantik case.

N4 — relaksasi attempt-lock berbasis-shortlist. Model berulang ditolak
`off-candidate-files` padahal file yang ia sentuh ADA di candidates.md
peringkat lain (bukti: 12184 r9 & r10 sama-sama menyentuh
django/urls/resolvers.py — kandidat #2 — di tengah attempt-1 yang terkunci
ke #1). >=INSIST_CANDIDATE_THRESHOLD penolakan utk kandidat sah yang SAMA
-> akhiri attempt dini + promosikan kandidat itu ke attempt berikutnya.
GOLD-BLIND mutlak: keputusan hanya dari perilaku model + shortlist produk;
file di LUAR shortlist tetap ditolak (pagar edit TIDAK dilonggarkan).
"""
from __future__ import annotations

import hashlib

# N1: berapa reply md5-identik BERUNTUN sebelum attempt diakhiri dini
# (3 = md5 sama 2x berturut-turut; keputusan §7).
DEGENERATE_REPLY_STREAK = 3
# N1b: berapa hit periode-2 (md5(N)==md5(N-2)) BERUNTUN sebelum attempt
# diakhiri dini (3 hit = A-B-A-B-A; promosi sweep 2026-07-23).
DEGENERATE_P2_STREAK = 3
# N4: berapa penolakan off-candidate-files utk kandidat sah yang SAMA
# sebelum lock dipindahkan ke kandidat itu (keputusan §7).
INSIST_CANDIDATE_THRESHOLD = 3


def reply_md5(reply: str) -> str:
    """md5 hex reply mentah (byte-identity — tanpa normalisasi, KH-21)."""
    return hashlib.md5((reply or "").encode("utf-8")).hexdigest()


class ReplyHashWatcher:
    """N1(+N1b): lacak streak reply byte-identik & siklus periode-2 (md5)
    dalam SATU attempt.

    Satu instance per attempt (sesi fresh = watcher fresh). `observe`
    dipanggil tiap reply; True = salah satu ambang tercapai -> caller
    mengakhiri attempt dini (break), TANPA menyuntik apa pun ke konteks.
    Pola yang menembak terbaca di `trigger` ("reply-hash" | "reply-hash-p2";
    streak lama preseden bila keduanya terpenuhi — reply konstan memicu
    kedua pola sekaligus).
    """

    def __init__(self, streak_limit: int = DEGENERATE_REPLY_STREAK,
                 p2_limit: int = DEGENERATE_P2_STREAK) -> None:
        self.streak_limit = streak_limit
        self.p2_limit = p2_limit
        self.last_md5: str | None = None
        self.prev2_md5: str | None = None   # md5 dua reply ke belakang
        self.streak = 0
        self.p2_streak = 0
        self.trigger: str | None = None

    def observe(self, reply: str) -> bool:
        h = reply_md5(reply)
        # N1b: hit periode-2 = identik dgn reply dua-ke-belakang.
        if self.prev2_md5 is not None and h == self.prev2_md5:
            self.p2_streak += 1
        else:
            self.p2_streak = 0
        if h == self.last_md5:
            self.streak += 1
        else:
            self.streak = 1
        self.prev2_md5 = self.last_md5
        self.last_md5 = h
        if self.streak >= self.streak_limit:
            self.trigger = "reply-hash"
        elif self.p2_streak >= self.p2_limit:
            self.trigger = "reply-hash-p2"
        return self.trigger is not None


def shortlist_strays(touched, candidate_files: list[str],
                     active_file: str) -> list[int]:
    """N4: peringkat (1-based) kandidat shortlist yang disentuh diff SELAIN
    kandidat aktif. File di luar shortlist TIDAK dihitung (pagar tetap).
    Path dinormalisasi lstrip("/") — idiom patch_static_result."""
    norm = [f.lstrip("/") for f in candidate_files]
    active = active_file.lstrip("/")
    ranks: set[int] = set()
    for p in touched:
        p = p.lstrip("/")
        if p != active and p in norm:
            ranks.add(norm.index(p) + 1)
    return sorted(ranks)


def record_insist(counts: dict[int, int], ranks: list[int],
                  threshold: int = INSIST_CANDIDATE_THRESHOLD) -> int | None:
    """N4: catat satu penolakan off-candidate-files per peringkat kandidat
    sah yang disentuh (mutasi `counts`, satu dict per attempt). Kembalikan
    peringkat PERTAMA yang mencapai ambang, atau None bila belum ada."""
    hit: int | None = None
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
        if counts[r] >= threshold and hit is None:
            hit = r
    return hit
