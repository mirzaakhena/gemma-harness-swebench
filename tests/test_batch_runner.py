"""Test logika murni batch runner RLFV (scripts/run_rlfv_batch.py).

Yang diuji hanya fungsi tanpa efek samping: parsing daftar case, pembacaan
antrean GPU, dan pemilihan nomor rerun. Orkestrasi docker/GPU tidak diuji di
sini — itu butuh mesin sungguhan.

Fokus utamanya dua invarian yang lahir dari insiden nyata:
- `parse_waiting` harus gagal-aman ke arah MENUNGGU saat output tak terbaca
- `next_free_rerun` tidak boleh pernah memakai ulang slot yang sudah ada
  (insiden 2026-07-20: run dir di-rename agar slot r1 bisa dipakai ulang,
  memecah konsistensi nama folder vs run_id)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from run_rlfv_batch import (  # noqa: E402
    next_free_rerun,
    parse_case_list,
    parse_waiting,
    qualified_rerun,
)


# --- parse_case_list -------------------------------------------------------

def test_parse_case_list_strips_blanks_and_comments():
    text = "\n".join([
        "django__django-11039",
        "",
        "# ini komentar",
        "  django__django-11179  ",
        "astropy__astropy-6938  # komentar di ujung baris",
    ])
    assert parse_case_list(text) == [
        "django__django-11039",
        "django__django-11179",
        "astropy__astropy-6938",
    ]


def test_parse_case_list_empty_input():
    assert parse_case_list("") == []
    assert parse_case_list("\n\n#cuma komentar\n") == []


# --- parse_waiting ---------------------------------------------------------

def test_parse_waiting_reads_queue_line():
    out = ("GPU0 util=100% mem=1/2MB\n"
           "vLLM queue: {'running': 4, 'waiting': 0}")
    assert parse_waiting(out) == 0


def test_parse_waiting_nonzero():
    assert parse_waiting("vLLM queue: {'running': 2, 'waiting': 3}") == 3


def test_parse_waiting_unreadable_returns_none_not_zero():
    """None != 0 — pemanggil memperlakukan None sebagai sibuk (gagal-aman)."""
    assert parse_waiting("koneksi gagal") is None
    assert parse_waiting("") is None


# --- next_free_rerun -------------------------------------------------------

def test_next_free_rerun_starts_at_one(tmp_path):
    assert next_free_rerun(tmp_path, "r-dev", "django__django-1") == 1


def test_next_free_rerun_skips_existing(tmp_path):
    (tmp_path / "r-dev--django__django-1--r1").mkdir()
    (tmp_path / "r-dev--django__django-1--r2").mkdir()
    assert next_free_rerun(tmp_path, "r-dev", "django__django-1") == 3


def test_next_free_rerun_never_reuses_occupied_slot(tmp_path):
    """Invarian anti-insiden: slot terpakai tidak boleh dikembalikan."""
    for n in (1, 2, 3):
        (tmp_path / f"r-dev--django__django-1--r{n}").mkdir()
    got = next_free_rerun(tmp_path, "r-dev", "django__django-1")
    assert got == 4
    assert not (tmp_path / f"r-dev--django__django-1--r{got}").exists()


def test_next_free_rerun_ignores_other_cases(tmp_path):
    (tmp_path / "r-dev--django__django-OTHER--r1").mkdir()
    assert next_free_rerun(tmp_path, "r-dev", "django__django-1") == 1


# --- qualified_rerun -------------------------------------------------------

def _mk_run(root: Path, campaign: str, case: str, n: int, pass_l1):
    d = root / f"{campaign}--{case}--r{n}"
    d.mkdir(parents=True)
    payload = {"run_id": f"{campaign}--{case}--r{n}"}
    if pass_l1 is not None:
        payload["pass_l1"] = pass_l1
    (d / "verdict.json").write_text(json.dumps(payload), encoding="utf-8")
    return d


def test_qualified_rerun_none_when_no_runs(tmp_path):
    assert qualified_rerun(tmp_path, "r-dev", "django__django-1") is None


def test_qualified_rerun_picks_qualified_not_largest(tmp_path):
    """Pelajaran 13660: r3 wrong-logic, yang qualified terakhir r2."""
    _mk_run(tmp_path, "r-dev", "django__django-1", 1, True)
    _mk_run(tmp_path, "r-dev", "django__django-1", 2, True)
    _mk_run(tmp_path, "r-dev", "django__django-1", 3, False)
    assert qualified_rerun(tmp_path, "r-dev", "django__django-1") == 2


def test_qualified_rerun_ignores_missing_verdict(tmp_path):
    (tmp_path / "r-dev--django__django-1--r1").mkdir()
    _mk_run(tmp_path, "r-dev", "django__django-1", 2, True)
    assert qualified_rerun(tmp_path, "r-dev", "django__django-1") == 2


def test_qualified_rerun_none_when_all_failed(tmp_path):
    _mk_run(tmp_path, "r-dev", "django__django-1", 1, False)
    _mk_run(tmp_path, "r-dev", "django__django-1", 2, None)
    assert qualified_rerun(tmp_path, "r-dev", "django__django-1") is None
