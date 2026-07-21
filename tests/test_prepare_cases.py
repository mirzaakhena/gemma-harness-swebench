"""Tests untuk scripts/prepare_cases.py — fokus R18/KL-G3-1.

R18 = fail-fast validasi bahwa gold.patch PARSE bersih saat case-setup
(`git apply --numstat`, cek parse tanpa menyentuh worktree). Menjaga kelas
korupsi KH-16: body hunk kurang baris konteks trailing vs header `@@` →
`git apply` "corrupt patch" → flip short-circuit → verdict wrong-logic salah.
"""
from __future__ import annotations

import pytest

from scripts.prepare_cases import validate_gold_patch_parses

# Well-formed unified diff: header @@ -1,3 +1,4 @@ punya 3 baris konteks/hapus
# di sisi lama (3 baris ' ') dan 4 di sisi baru (3 ' ' + 1 '+'). Konsisten.
GOOD_PATCH = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 line1
 line2
+inserted
 line3
"""

# Malformed: header mengklaim 3 baris konteks di sisi lama (@@ -1,3 +1,4 @@)
# tapi body cuma menyediakan 2 baris konteks (line3 trailing hilang) —
# meniru KH-16 (body hunk kurang 1 baris konteks trailing vs header @@).
CORRUPT_PATCH = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 line1
 line2
+inserted
"""


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_bytes(text.encode("utf-8"))
    return p


def test_validate_gold_patch_parses_accepts_wellformed(tmp_path):
    good = _write(tmp_path, "gold.patch", GOOD_PATCH)
    # Tidak boleh raise untuk patch yang parse bersih.
    validate_gold_patch_parses(good)


def test_validate_gold_patch_parses_raises_on_corrupt(tmp_path):
    bad = _write(tmp_path, "gold.patch", CORRUPT_PATCH)
    with pytest.raises(Exception) as exc:
        validate_gold_patch_parses(bad)
    msg = str(exc.value)
    # Pesan harus deskriptif: menyebut nama case/patch + error git.
    assert "gold.patch" in msg
    assert "corrupt patch" in msg
