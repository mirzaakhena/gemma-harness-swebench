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
