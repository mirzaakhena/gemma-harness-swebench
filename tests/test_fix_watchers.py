"""Test watcher loop FIX (N1 + N4) — logika murni tanpa docker/HTTP.

Lever G2 (docs/rekomendasi-lever-dari-taksonomi.md §7):
N1 — watcher reply-hash: 3 reply md5-identik beruntun = loop degenerat
     temp-0 (bukti 12184 r12: 32 reply identik t9–t40) -> akhiri attempt.
N4 — relaksasi attempt-lock: >=3 penolakan off-candidate-files utk file
     yang ADA di shortlist -> pindahkan lock ke kandidat itu.
"""
from harness.stages.fix_watchers import (DEGENERATE_REPLY_STREAK,
                                         INSIST_CANDIDATE_THRESHOLD,
                                         ReplyHashWatcher, record_insist,
                                         shortlist_strays)


# --- N1: ReplyHashWatcher ---------------------------------------------------

def test_streak_constants_are_three():
    # Ambang = konstanta bernama, mudah diubah; default keputusan §7 = 3.
    assert DEGENERATE_REPLY_STREAK == 3
    assert INSIST_CANDIDATE_THRESHOLD == 3


def test_reply_hash_triggers_on_third_identical():
    w = ReplyHashWatcher()
    assert w.observe("same reply") is False   # 1x: baseline
    assert w.observe("same reply") is False   # 2x: md5 sama 1x berturut
    assert w.observe("same reply") is True    # 3x: md5 sama 2x berturut


def test_reply_hash_resets_on_different_reply():
    w = ReplyHashWatcher()
    w.observe("A")
    w.observe("A")
    assert w.observe("B") is False            # beda -> streak mulai ulang
    assert w.observe("B") is False
    assert w.observe("B") is True


def test_reply_hash_is_byte_identity_not_normalized():
    # KH-21: trigger byte-identity — whitespace beda = reply beda.
    w = ReplyHashWatcher()
    w.observe("x")
    assert w.observe("x ") is False
    assert w.observe("x") is False


def test_reply_hash_custom_streak_limit():
    w = ReplyHashWatcher(streak_limit=2)
    assert w.observe("r") is False
    assert w.observe("r") is True


# --- N4: shortlist_strays + record_insist -----------------------------------

CAND_FILES = ["django/urls/base.py", "django/urls/resolvers.py",
              "django/core/handlers/exception.py"]


def test_shortlist_strays_maps_stray_to_rank():
    # Diff menyentuh kandidat aktif (#1) + kandidat #2 -> stray sah = [2].
    ranks = shortlist_strays(
        ("django/urls/base.py", "django/urls/resolvers.py"),
        CAND_FILES, "django/urls/base.py")
    assert ranks == [2]


def test_shortlist_strays_ignores_files_outside_shortlist():
    # Pagar edit TIDAK dilonggarkan: file di luar shortlist bukan sinyal.
    ranks = shortlist_strays(
        ("django/urls/base.py", "django/http/response.py"),
        CAND_FILES, "django/urls/base.py")
    assert ranks == []


def test_shortlist_strays_normalizes_leading_slash():
    ranks = shortlist_strays(
        ("/django/urls/resolvers.py",),
        CAND_FILES, "/django/urls/base.py")
    assert ranks == [2]


def test_shortlist_strays_multiple_ranks_sorted_dedup():
    ranks = shortlist_strays(
        ("django/core/handlers/exception.py", "django/urls/resolvers.py",
         "django/urls/resolvers.py"),
        CAND_FILES, "django/urls/base.py")
    assert ranks == [2, 3]


def test_record_insist_hits_threshold_at_three():
    counts: dict = {}
    assert record_insist(counts, [2]) is None
    assert record_insist(counts, [2]) is None
    assert record_insist(counts, [2]) == 2
    assert counts[2] == 3


def test_record_insist_counts_per_rank_not_summed():
    # 2 penolakan utk #2 + 1 utk #3 BUKAN 3 utk satu kandidat.
    counts: dict = {}
    assert record_insist(counts, [2]) is None
    assert record_insist(counts, [3]) is None
    assert record_insist(counts, [2]) is None
    assert record_insist(counts, [3]) is None


def test_record_insist_custom_threshold():
    counts: dict = {}
    assert record_insist(counts, [1], threshold=1) == 1
