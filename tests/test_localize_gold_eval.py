"""Test kriteria shortlist LOCALIZE (keputusan Mirza 2026-07-19 via buttons):
qualified = ada kandidat ∈ file gold — fase FIX bisa mengiterasi shortlist,
yang penting jawaban benar masuk daftar pendek. Pilihan utama (chosen file)
tetap dicatat sebagai advisory. Pagar anti-gaming: kandidat 2–3 file
(test di test_localize_gates)."""

GOLD = """\
diff --git a/django/db/models/enums.py b/django/db/models/enums.py
--- a/django/db/models/enums.py
+++ b/django/db/models/enums.py
@@ -60,7 +60,13 @@ def values(cls):

 class Choices(enum.Enum, metaclass=ChoicesMeta):
-    pass
+
+    def __str__(self):
+        return str(self.value)

"""


def test_shortlist_qualified_when_any_candidate_hits_gold():
    from eval.localize_gold_eval import gold_touched_files, shortlist_qualified
    gold = gold_touched_files(GOLD)
    ok, criterion = shortlist_qualified(
        ["django/db/models/fields/__init__.py", "django/db/models/enums.py"],
        "django/db/models/fields/__init__.py", gold)
    assert ok is True
    assert criterion == "shortlist-v2"


def test_shortlist_not_qualified_when_no_candidate_hits_gold():
    from eval.localize_gold_eval import gold_touched_files, shortlist_qualified
    gold = gold_touched_files(GOLD)
    ok, criterion = shortlist_qualified(
        ["django/db/models/fields/__init__.py", "django/db/models/base.py"],
        "django/db/models/base.py", gold)
    assert ok is False
    assert criterion == "shortlist-v2"


def test_shortlist_tolerates_leading_slash():
    from eval.localize_gold_eval import gold_touched_files, shortlist_qualified
    gold = gold_touched_files(GOLD)
    ok, _ = shortlist_qualified(["/django/db/models/enums.py"], "x.py", gold)
    assert ok is True


def test_fallback_chosen_file_when_no_candidates():
    # Run era pra-L#2 tidak punya candidates.md — kriteria jatuh ke chosen
    # file (kompatibel mundur, ditandai criterion).
    from eval.localize_gold_eval import gold_touched_files, shortlist_qualified
    gold = gold_touched_files(GOLD)
    ok, criterion = shortlist_qualified(None, "django/db/models/enums.py", gold)
    assert ok is True and criterion == "chosen-file-v1"
    ok2, _ = shortlist_qualified(None, "django/db/models/base.py", gold)
    assert ok2 is False
