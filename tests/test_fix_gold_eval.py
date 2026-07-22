"""Test eval gold FIX — file_match + overlap advisory (fixture diff
sintetis). Fungsi utama: menandai false-PASS (flip product tapi file/arah
!= gold) untuk autopsi manusia — dev realm, product tetap gold-blind."""
import json
import sys

from eval.fix_gold_eval import evaluate_fix_gold

GOLD = """diff --git a/django/db/models/enums.py b/django/db/models/enums.py
--- a/django/db/models/enums.py
+++ b/django/db/models/enums.py
@@ -60,7 +60,13 @@ def values(cls):
+    def __str__(self):
+        return str(self.value)
diff --git a/tests/model_enums/tests.py b/tests/model_enums/tests.py
--- a/tests/model_enums/tests.py
+++ b/tests/model_enums/tests.py
@@ -1,3 +1,4 @@
+import x
"""

FIX_SAME_SITE = """diff --git a/django/db/models/enums.py b/django/db/models/enums.py
--- a/django/db/models/enums.py
+++ b/django/db/models/enums.py
@@ -58,4 +58,8 @@ class Choices:
+    def __str__(self):
+        return str(self.value)
"""

FIX_WRONG_FILE = """diff --git a/django/db/models/base.py b/django/db/models/base.py
--- a/django/db/models/base.py
+++ b/django/db/models/base.py
@@ -1,3 +1,4 @@
+import x
"""

FIX_SAME_FILE_FAR_AWAY = """diff --git a/django/db/models/enums.py b/django/db/models/enums.py
--- a/django/db/models/enums.py
+++ b/django/db/models/enums.py
@@ -400,3 +400,4 @@ def tail():
+    pass
"""


def test_file_match_and_overlap():
    r = evaluate_fix_gold(FIX_SAME_SITE, GOLD)
    assert r["file_match"] is True
    assert r["line_overlap"] is True  # 58-65 overlap hunk gold 60-72


def test_wrong_file_no_match_overlap_none():
    r = evaluate_fix_gold(FIX_WRONG_FILE, GOLD)
    assert r["file_match"] is False and r["line_overlap"] is None


def test_same_file_no_overlap_is_advisory():
    r = evaluate_fix_gold(FIX_SAME_FILE_FAR_AWAY, GOLD)
    assert r["file_match"] is True and r["line_overlap"] is False


def test_gold_files_reported_sorted():
    r = evaluate_fix_gold(FIX_SAME_SITE, GOLD)
    assert r["gold_files"] == ["django/db/models/enums.py",
                               "tests/model_enums/tests.py"]
    assert r["touched_files"] == ["django/db/models/enums.py"]


# --- R15: detektor dua-arah region-hunk (LV-14) -----------------------------
# line_overlap menyesatkan dua arah (11999 superset overlap=true; 12907
# rewrite overlap=false). R15: hitung jumlah region hunk gold vs patch per
# file; mismatch + line_overlap=true -> flag. Realm EVAL (gold-aware sah);
# nilai utk papan skor & autopsi, bukan loop model.

R15_GOLD_2HUNK = """diff --git a/django/db/models/enums.py b/django/db/models/enums.py
--- a/django/db/models/enums.py
+++ b/django/db/models/enums.py
@@ -60,7 +60,13 @@ def values(cls):
+    def __str__(self):
+        return str(self.value)
@@ -120,3 +126,4 @@ def tail():
+    x = 1
diff --git a/tests/model_enums/tests.py b/tests/model_enums/tests.py
--- a/tests/model_enums/tests.py
+++ b/tests/model_enums/tests.py
@@ -1,3 +1,4 @@
+import x
"""

R15_FIX_SUBSET = """diff --git a/django/db/models/enums.py b/django/db/models/enums.py
--- a/django/db/models/enums.py
+++ b/django/db/models/enums.py
@@ -58,4 +58,8 @@ class Choices:
+    def __str__(self):
+        return str(self.value)
"""

R15_FIX_SUPERSET = """diff --git a/django/db/models/enums.py b/django/db/models/enums.py
--- a/django/db/models/enums.py
+++ b/django/db/models/enums.py
@@ -58,4 +58,8 @@ class Choices:
+    def __str__(self):
+        return str(self.value)
@@ -120,3 +124,4 @@ def tail():
+    x = 1
@@ -400,3 +401,4 @@ def far():
+    pass
"""

R15_FIX_SUBSET_FAR = """diff --git a/django/db/models/enums.py b/django/db/models/enums.py
--- a/django/db/models/enums.py
+++ b/django/db/models/enums.py
@@ -400,3 +400,4 @@ def far():
+    pass
"""


def test_r15_subset_regions_flagged_when_overlap_green():
    # 14365-style: patch 1 region vs gold 2 di file yang sama, overlap hijau
    # -> hijau-longgar tertandai.
    r = evaluate_fix_gold(R15_FIX_SUBSET, R15_GOLD_2HUNK)
    assert r["line_overlap"] is True
    assert r["hunk_regions"] == {
        "django/db/models/enums.py": {"gold": 2, "fix": 1}}
    assert r["region_mismatch"] == {"django/db/models/enums.py": "subset"}
    assert r["region_flag"] is True


def test_r15_superset_regions_flagged_when_overlap_green():
    # 11999-style: patch 3 region vs gold 2, salah satu overlap -> flag.
    r = evaluate_fix_gold(R15_FIX_SUPERSET, R15_GOLD_2HUNK)
    assert r["line_overlap"] is True
    assert r["hunk_regions"] == {
        "django/db/models/enums.py": {"gold": 2, "fix": 3}}
    assert r["region_mismatch"] == {"django/db/models/enums.py": "superset"}
    assert r["region_flag"] is True


def test_r15_equal_regions_no_flag():
    # Blind-spot terdokumentasi (12284): over-broad DI DALAM satu region
    # (jumlah region gold==model) TIDAK tertangkap — jangan baca flag False
    # sebagai "patch setara gold" (divergensi intra-hunk butuh bacaan diff).
    r = evaluate_fix_gold(FIX_SAME_SITE, GOLD)
    assert r["hunk_regions"] == {
        "django/db/models/enums.py": {"gold": 1, "fix": 1}}
    assert r["region_mismatch"] == {}
    assert r["region_flag"] is False


def test_r15_mismatch_recorded_but_flag_false_when_overlap_red():
    # Overlap sudah merah (advisory lama) -> mismatch tercatat sbg data,
    # flag R15 khusus utk kelas hijau-longgar (overlap=true).
    r = evaluate_fix_gold(R15_FIX_SUBSET_FAR, R15_GOLD_2HUNK)
    assert r["line_overlap"] is False
    assert r["region_mismatch"] == {"django/db/models/enums.py": "subset"}
    assert r["region_flag"] is False


def test_r15_wrong_file_fields_none():
    # Konsisten dgn line_overlap: file salah -> region fields tak bermakna.
    r = evaluate_fix_gold(FIX_WRONG_FILE, GOLD)
    assert r["hunk_regions"] is None
    assert r["region_mismatch"] is None
    assert r["region_flag"] is None


def test_r15_counts_only_for_touched_files():
    # File gold yang TIDAK disentuh patch (test file resmi) bukan urusan
    # model (semantik subset file_match) -> tak ikut dihitung/di-flag.
    r = evaluate_fix_gold(R15_FIX_SUBSET, R15_GOLD_2HUNK)
    assert "tests/model_enums/tests.py" not in r["hunk_regions"]


def test_cli_writes_gold_eval_json(tmp_path, monkeypatch):
    from eval import fix_gold_eval
    run = tmp_path / "f-dev" / "f-dev--django__django-11422--r1" / "files"
    run.mkdir(parents=True)
    (run / "fix.diff").write_text(FIX_SAME_SITE, encoding="utf-8")
    gold = tmp_path / "gold.patch"
    gold.write_text(GOLD, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "fix_gold_eval.py", "--case", "django__django-11422", "--rerun", "1",
        "--gold", str(gold), "--artifacts", str(tmp_path)])
    assert fix_gold_eval.main() == 0
    out = json.loads((run.parent / "gold_eval.json")
                     .read_text(encoding="utf-8"))
    assert out["file_match"] is True and out["case"] == "django__django-11422"


def test_cli_missing_diff_returns_error(tmp_path, monkeypatch):
    from eval import fix_gold_eval
    gold = tmp_path / "gold.patch"
    gold.write_text(GOLD, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "fix_gold_eval.py", "--case", "django__django-11422", "--rerun", "1",
        "--gold", str(gold), "--artifacts", str(tmp_path)])
    assert fix_gold_eval.main() == 1
