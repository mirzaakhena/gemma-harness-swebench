"""Tests untuk R5 no-progress watcher (pure decision function).

Lever R5 (DESAIN FINAL Mirza 2026-07-21): watcher mekanis intra-run di driver
REPRODUCE. Sinyal HANYA dari base-world yang disaksikan driver (gold-blind by
construction). Aksi dua-langkah: (1) inject pesan UNIK ke feedback; (2) hanya
bila trigger PERSISTS setelah injeksi -> early-exit `break` (BUKAN emit_abort,
biar artefak tersalin & gate memvonis — hindari dua-penulis-verdict).

TDD: tes ini ditulis SEBELUM implementasi (fase merah).
"""
from pathlib import Path

from harness.stages.no_progress import (K_NO_PROGRESS, X_OBSERVE_FAIL,
                                        NoProgressDecision,
                                        no_progress_decision)


# --- Trigger #1: >=K byte-identik reply berturut-turut ---------------------

def test_identical_replies_inject_then_break():
    K = K_NO_PROGRESS
    replies = ["same reply"] * K
    counts = [1] * K  # aksi ada tapi identik -> tetap no-progress
    d = no_progress_decision(replies, counts, turn_idx=K,
                             observed_fail=True, already_injected=set())
    assert d.action == "inject"
    assert d.trigger == "identical-replies"
    assert isinstance(d, NoProgressDecision)

    # Persists setelah injeksi (masih identik di cek berikutnya) -> break.
    d2 = no_progress_decision(replies + ["same reply"], counts + [1],
                              turn_idx=K + 1, observed_fail=True,
                              already_injected={"identical-replies"})
    assert d2.action == "break"
    assert d2.trigger == "identical-replies"


def test_injected_message_is_unique_per_occurrence():
    K = K_NO_PROGRESS
    replies = ["x"] * K
    counts = [1] * K
    m1 = no_progress_decision(replies, counts, turn_idx=K, observed_fail=True,
                              already_injected=set()).message
    m2 = no_progress_decision(replies, counts, turn_idx=K + 7,
                              observed_fail=True,
                              already_injected=set()).message
    # Di temp 0.0 pesan identik tak akan mengusik fixed-point; wajib unik.
    assert m1 != m2
    assert str(K) in m1  # menyebut fakta konkret (jumlah reply identik)
    assert str(K + 7) not in m1 and str(K + 7) in m2  # nomor turn = pembeda


def test_whitespace_only_differences_count_as_identical():
    replies = ["reply\n", "reply  ", "reply\t\n"]
    d = no_progress_decision(replies, [1, 1, 1], turn_idx=5,
                             observed_fail=True, already_injected=set())
    assert d.action == "inject"
    assert d.trigger == "identical-replies"


# --- Trigger #1b: periode-2 (r[N] == r[N-2], A-B-A-B) ----------------------
# Promosi sweep 2026-07-23: siklus periode-2 LOLOS trigger identik-3
# (spesimen 15902 r2/r3 fase R; 19 run periode-2 murni di korpus).

def test_period2_replies_inject_then_break():
    K = K_NO_PROGRESS
    replies = ["form A", "form B", "form A", "form B", "form A"]  # 3 hit p2
    counts = [1] * len(replies)
    d = no_progress_decision(replies, counts, turn_idx=5,
                             observed_fail=True, already_injected=set())
    assert d.action == "inject"
    assert d.trigger == "period-2-replies"
    assert str(5) in d.message  # pesan unik: menyebut nomor turn

    d2 = no_progress_decision(replies + ["form B"], counts + [1],
                              turn_idx=6, observed_fail=True,
                              already_injected={"period-2-replies"})
    assert d2.action == "break"
    assert d2.trigger == "period-2-replies"
    assert K == 3  # jendela = K perbandingan jarak-2 (5 reply)


def test_period2_below_window_returns_none():
    # A-B-A-B = baru 2 perbandingan (< K) -> belum sinyal.
    d = no_progress_decision(["form A", "form B", "form A", "form B"],
                             [1, 1, 1, 1], turn_idx=4,
                             observed_fail=True, already_injected=set())
    assert d.action == "none"


def test_period2_normalizes_whitespace_edges():
    replies = ["form A\n", "form B", "form A  ", "form B\t", "form A"]
    d = no_progress_decision(replies, [1] * 5, turn_idx=5,
                             observed_fail=True, already_injected=set())
    assert d.action == "inject"
    assert d.trigger == "period-2-replies"


def test_constant_replies_prefer_identical_trigger_over_period2():
    # Reply konstan memenuhi keduanya; label identical-replies yang menang.
    d = no_progress_decision(["x"] * 5, [1] * 5, turn_idx=5,
                             observed_fail=True, already_injected=set())
    assert d.trigger == "identical-replies"


def test_period2_message_hygiene():
    m = no_progress_decision(["A", "B", "A", "B", "A"], [1] * 5, turn_idx=7,
                             observed_fail=True,
                             already_injected=set()).message
    low = m.lower()
    assert "watcher" not in low and "detector" not in low  # §4b
    for w in ("kamu", "jalankan", "tulis ", "berkas", "balasan"):  # §4
        assert w not in low


# --- Trigger #2: >=K turn beruntun dengan 0 aksi ter-parse -----------------

def test_zero_action_turns_inject_then_break():
    K = K_NO_PROGRESS
    replies = [f"prose turn {i}" for i in range(K)]  # teks beda, tapi 0 aksi
    counts = [0] * K
    d = no_progress_decision(replies, counts, turn_idx=10,
                             observed_fail=False, already_injected=set())
    assert d.action == "inject"
    assert d.trigger == "zero-actions"

    d2 = no_progress_decision(replies + ["prose more"], counts + [0],
                              turn_idx=11, observed_fail=False,
                              already_injected={"zero-actions"})
    assert d2.action == "break"
    assert d2.trigger == "zero-actions"


# --- Trigger #8: turn >= X dan observed_fail masih False (inject-only) ------

def test_observed_fail_never_past_x_injects_guidance():
    d = no_progress_decision(["r1", "r2", "r3"], [1, 1, 1],
                             turn_idx=X_OBSERVE_FAIL, observed_fail=False,
                             already_injected=set())
    assert d.action == "inject"
    assert d.trigger == "not-observed"
    assert "observed" in d.message.lower()


def test_not_observed_is_inject_only_never_breaks():
    # #8 tak pernah eskalasi ke break — sudah di-inject -> diam (none).
    d = no_progress_decision(["r1", "r2", "r3"], [1, 1, 1],
                             turn_idx=X_OBSERVE_FAIL + 5, observed_fail=False,
                             already_injected={"not-observed"})
    assert d.action == "none"


def test_not_observed_silent_once_failure_observed():
    d = no_progress_decision(["r1", "r2", "r3"], [1, 1, 1],
                             turn_idx=X_OBSERVE_FAIL + 5, observed_fail=True,
                             already_injected=set())
    assert d.action == "none"


# --- Negatif: run normal / di bawah ambang ---------------------------------

def test_normal_progressing_run_returns_none():
    d = no_progress_decision(["do A", "do B", "do C"], [1, 2, 1],
                             turn_idx=5, observed_fail=True,
                             already_injected=set())
    assert d.action == "none"


def test_below_threshold_returns_none():
    d = no_progress_decision(["same", "same"], [0, 0], turn_idx=2,
                             observed_fail=False, already_injected=set())
    assert d.action == "none"


# --- Higiene bahasa & mekanisme (§4 / §4b) ---------------------------------

def test_messages_are_english_and_dont_narrate_mechanism():
    msgs = []
    msgs.append(no_progress_decision(["x", "x", "x"], [1, 1, 1], turn_idx=5,
                                     observed_fail=True,
                                     already_injected=set()).message)
    msgs.append(no_progress_decision(["a", "b", "c"], [0, 0, 0], turn_idx=6,
                                     observed_fail=False,
                                     already_injected=set()).message)
    msgs.append(no_progress_decision(["a", "b", "c"], [1, 1, 1],
                                     turn_idx=X_OBSERVE_FAIL,
                                     observed_fail=False,
                                     already_injected=set()).message)
    for m in msgs:
        assert m
        low = m.lower()
        # §4b: jangan narasikan mekanisme enforcement (watcher/detector).
        assert "watcher" not in low
        assert "detector" not in low
        # §4: model-facing text = English.
        for w in ("kamu", "jalankan", "tulis ", "berkas", "balasan"):
            assert w not in low


# --- Wiring driver: break (BUKAN emit_abort); driver tak menulis verdict ----

def test_driver_uses_break_not_abort_for_no_progress():
    import harness.stages.run_reproduce_gemma as drv
    src = Path(drv.__file__).read_text(encoding="utf-8")
    assert "no_progress_decision" in src
    # Aksi trigger yang persist = `break` biasa (bukan abort).
    assert 'action == "break"' in src
    # emit_abort tetap HANYA di jalur abort sungguhan — 3 PEMANGGILAN sejak
    # lever infra-abort: preflight gagal, ChatTransportError, crash generik
    # (bentuk `emit_abort(em, ...)`; definisi `def emit_abort(em:` bukan call).
    # Jalur no-progress TIDAK memanggilnya (break biasa, gate yang memvonis).
    assert src.count("emit_abort(em,") == 3
