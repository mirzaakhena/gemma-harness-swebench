"""R5 — no-progress watcher (fungsi keputusan MURNI, tanpa docker/IO).

DESAIN FINAL Mirza 2026-07-21 (docs/rekomendasi-lever-dari-taksonomi.md §1 R5).
Di temp 0.0 model kecil kerap terperangkap fixed-point (R-1/R-2/R-4/R-6):
me-regenerasi reply byte-identik ~35+ turn, atau 0 aksi ter-parse berulang,
atau tak pernah menyaksikan kegagalan. Satu-satunya jalan keluar di temp 0
adalah MENGUBAH KONTEKS.

Pola (Mirza): trigger MEKANIS dari sinyal yang harness saksikan sendiri di
BASE-WORLD (gold-blind by construction) -> aksi dua langkah:
  1. INJECT pesan mekanis UNIK (nomor turn + fakta konkret) ke feedback_parts.
     Unik = wajib: pesan identik tak akan mengusik attractor temp-0.
  2. HANYA bila trigger PERSISTS setelah injeksi (masih terpicu di cek
     berikutnya) -> early-exit `break` (BUKAN emit_abort). `break` membiarkan
     salinan artefak akhir jalan & GATE memvonis — hindari konflik
     dua-penulis-verdict (driver TIDAK pernah menulis verdict; prinsip §5).

Trigger yang diimplementasi (subset deterministik bernilai tertinggi):
  #1 >=K reply byte-identik berturut (normalisasi whitespace) -> inject->break.
  #2 >=K turn beruntun dengan 0 aksi ter-parse -> inject->break.
  #8 turn >= X dan observed_fail masih False -> inject-only (tak eskalasi break).

Semua sinyal berasal dari yang driver saksikan tanpa gold. Fungsi ini murni:
tidak menyentuh docker/endpoint/filesystem — sehingga unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass

# Ambang kalibrasi (konstanta modul; budget default run = 40 turn).
K_NO_PROGRESS = 3   # #1/#2: berapa kali beruntun sebelum dianggap macet.
X_OBSERVE_FAIL = 15  # #8: turn saat "belum menyaksikan FAIL" jadi sinyal.

# Nama trigger (identifier internal, BUKAN model-facing).
_T_IDENTICAL = "identical-replies"
_T_ZERO_ACTIONS = "zero-actions"
_T_NOT_OBSERVED = "not-observed"


@dataclass(frozen=True)
class NoProgressDecision:
    action: str                     # "none" | "inject" | "break"
    trigger: str | None = None
    message: str | None = None      # diisi hanya untuk action == "inject"


def _norm(reply: str) -> str:
    """Normalisasi sebelum banding-identitas: buang whitespace tepi supaya
    beda pipe/whitespace sepele tak dianggap 'progres'."""
    return (reply or "").strip()


def _identical_tail(replies: list[str], k: int) -> bool:
    if len(replies) < k:
        return False
    tail = {_norm(r) for r in replies[-k:]}
    return len(tail) == 1


def _zero_action_tail(counts: list[int], k: int) -> bool:
    if len(counts) < k:
        return False
    return all(c == 0 for c in counts[-k:])


def _identical_msg(turn_idx: int, k: int) -> str:
    return (f"Turn {turn_idx}: your last {k} replies were byte-identical. "
            "Repeating the same reply cannot change anything. Take a "
            "different, concrete next step now: open a relevant source file "
            "with a ```bash action to read the real code, or write your "
            "script to ```file:/testbed/.pipe/repro.py and run it with a "
            "```bash action.")


def _zero_action_msg(turn_idx: int, k: int) -> str:
    return (f"Turn {turn_idx}: your last {k} replies contained no runnable "
            "action block, so nothing ran. To move forward you must act: "
            "write a ```bash command, a ```file:/testbed/.pipe/repro.py "
            "block, or submit the ```repro.md block. Write your next step as "
            "a fenced action block now.")


def _not_observed_msg(turn_idx: int) -> str:
    return (f"Turn {turn_idx}: you have not yet observed the failure — no run "
            "has printed REPRO_STATUS: FAIL. Re-read the issue, then write "
            "a ```file:/testbed/.pipe/repro.py that reproduces the reported "
            "behaviour and run it with a ```bash action to see it fail.")


def no_progress_decision(recent_replies: list[str],
                         recent_action_counts: list[int],
                         turn_idx: int,
                         observed_fail: bool,
                         already_injected,
                         K: int = K_NO_PROGRESS,
                         X: int = X_OBSERVE_FAIL) -> NoProgressDecision:
    """Putuskan aksi watcher untuk turn saat ini (fungsi MURNI).

    Args:
      recent_replies: seluruh reply asisten sejauh ini (tail dipakai).
      recent_action_counts: jumlah aksi ter-parse per turn (paralel replies).
      turn_idx: nomor turn 1-based saat ini (dipakai untuk pesan UNIK).
      observed_fail: apakah REPRO_STATUS: FAIL sudah pernah tersaksikan.
      already_injected: himpunan nama-trigger yang SUDAH di-inject (caller
        menambah nama setelah aksi "inject"); dipakai untuk deteksi PERSISTS.
      K, X: ambang kalibrasi.

    Returns: NoProgressDecision(action in {"none","inject","break"}).
    """
    already = set(already_injected or ())
    identical = _identical_tail(recent_replies, K)
    zero_actions = _zero_action_tail(recent_action_counts, K)

    # Langkah 2 (eskalasi): trigger yang SUDAH di-inject dan MASIH terpicu ->
    # break. Caller memakai `break` (bukan emit_abort) — biar gate memvonis.
    if identical and _T_IDENTICAL in already:
        return NoProgressDecision("break", trigger=_T_IDENTICAL)
    if zero_actions and _T_ZERO_ACTIONS in already:
        return NoProgressDecision("break", trigger=_T_ZERO_ACTIONS)

    # Langkah 1 (kemunculan pertama): inject pesan UNIK.
    if identical:
        return NoProgressDecision("inject", trigger=_T_IDENTICAL,
                                  message=_identical_msg(turn_idx, K))
    if zero_actions:
        return NoProgressDecision("inject", trigger=_T_ZERO_ACTIONS,
                                  message=_zero_action_msg(turn_idx, K))

    # Trigger #8: inject-only (tak pernah eskalasi ke break).
    if turn_idx >= X and not observed_fail and _T_NOT_OBSERVED not in already:
        return NoProgressDecision("inject", trigger=_T_NOT_OBSERVED,
                                  message=_not_observed_msg(turn_idx))

    return NoProgressDecision("none")
