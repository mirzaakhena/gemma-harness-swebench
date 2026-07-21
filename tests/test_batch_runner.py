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

import run_rlfv_batch  # noqa: E402
from run_rlfv_batch import (  # noqa: E402
    dedup_results,
    next_free_rerun,
    parse_case_list,
    parse_waiting,
    qualified_rerun,
    should_prune_fix,
    wait_for_gpu,
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


# --- dedup_results (R6: papan skor batch tahan-resume) ---------------------
# Resume meng-append `results` ke state lama (run_rlfv_batch.py:350-370), jadi
# satu case bisa muncul >1 kali di list akumulasi (mis. crash lalu jalankan
# ulang). Ringkasan (:379-380) tak boleh menggelembung: tiap case dihitung
# SEKALI, entri TERAKHIR yang di-append untuk case itu yang menang.

def test_dedup_results_counts_each_case_once_across_resume():
    """Case yang sama muncul dua kali (resume rerun); dedup menyisakan satu
    entri per case dan entri terbaru menang."""
    results = [
        {"case": "django__django-1", "swebench_eval": {"resolved": False}},
        {"case": "astropy__astropy-2", "swebench_eval": {"resolved": True}},
        # resume: django-1 dijalankan ulang, kini resolved → entri terbaru menang
        {"case": "django__django-1", "swebench_eval": {"resolved": True}},
    ]
    deduped = dedup_results(results)
    assert len(deduped) == 2
    by_case = {r["case"]: r for r in deduped}
    assert by_case["django__django-1"]["swebench_eval"]["resolved"] is True
    # papan skor: resolved=2 dari 2 (bukan 2 dari 3 yang menggelembung)
    ok = sum(1 for r in deduped if (r.get("swebench_eval") or {}).get("resolved"))
    assert ok == 2
    assert len(deduped) == 2


def test_dedup_results_pruned_case_still_counts_as_failure():
    """Case self-pruned (skipped-fix-localize-miss, tanpa swebench_eval) TETAP
    gagal — dedup tak boleh mengubah semantik prune (fail-safe :86-117)."""
    results = [
        {"case": "django__django-1", "error": "skipped-fix-localize-miss",
         "localize_gold_miss": True},
        {"case": "astropy__astropy-2", "swebench_eval": {"resolved": True}},
    ]
    deduped = dedup_results(results)
    assert len(deduped) == 2
    ok = sum(1 for r in deduped if (r.get("swebench_eval") or {}).get("resolved"))
    assert ok == 1  # case ter-prune tidak dihitung resolved


def test_dedup_results_preserves_first_seen_order():
    """Urutan papan skor mengikuti kemunculan-pertama tiap case; rerun resume
    memutakhirkan nilai tanpa menggeser posisi."""
    results = [
        {"case": "a", "swebench_eval": {"resolved": True}},
        {"case": "b", "swebench_eval": {"resolved": False}},
        {"case": "a", "swebench_eval": {"resolved": False}},  # resume rerun a
    ]
    deduped = dedup_results(results)
    assert [r["case"] for r in deduped] == ["a", "b"]
    assert {r["case"]: r["swebench_eval"]["resolved"] for r in deduped} == {
        "a": False, "b": False}


def test_dedup_results_empty_and_no_dupes():
    assert dedup_results([]) == []
    single = [{"case": "x", "swebench_eval": {"resolved": True}}]
    assert dedup_results(single) == single


# --- wait_for_gpu (flag --allow-concurrent) --------------------------------

def test_wait_for_gpu_allow_concurrent_bypasses_gate(tmp_path, monkeypatch):
    """EKSPERIMEN: allow_concurrent=True submit langsung — gpu_check TIDAK
    dipanggil (bukan sekadar skip cek container, tapi bypass gate penuh)."""
    def _boom(*a, **k):
        raise AssertionError("gpu_check tak boleh dipanggil saat allow_concurrent")
    monkeypatch.setattr(run_rlfv_batch, "run", _boom)
    assert wait_for_gpu(tmp_path / "state.json", "django__django-1",
                        allow_concurrent=True) is True


# --- should_prune_fix (flag --prune-localize-miss) -------------------------
# Keputusan ORKESTRASI hemat-compute (batch runner, DI LUAR loop model): SKIP
# FIX bila gold_eval.json LOCALIZE menandai qualified=false (gold tak ada DI MANA
# PUN di shortlist). KL-G3-2/KH-17: keying `file_match` (pointed primer) terbukti
# false-prune — 13033 punya gold di candidate-2 (qualified=true), di-skip, dan
# saat di-re-run tanpa prune malah resolved=true. FIX mengiterasi SELURUH
# shortlist, jadi kriteria prune harus konsisten dengan itu: `qualified`.

def _write_gold_eval(tmp_path: Path, **fields) -> Path:
    payload = {"case": "x", "rerun": 1}
    payload.update({k: v for k, v in fields.items() if v is not ...})
    p = tmp_path / "gold_eval.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_should_prune_fix_disabled_always_false(tmp_path):
    """enabled=False → tak pernah prune, apa pun isi gold_eval (perilaku lama)."""
    p = _write_gold_eval(tmp_path, file_match=False, qualified=False)
    assert should_prune_fix(p, enabled=False) is False
    assert should_prune_fix({"qualified": False}, enabled=False) is False


def test_should_prune_fix_qualified_false_prunes(tmp_path):
    """gold tak ada di shortlist mana pun → prune (True)."""
    p = _write_gold_eval(tmp_path, file_match=False, qualified=False)
    assert should_prune_fix(p, enabled=True) is True
    assert should_prune_fix({"file_match": False, "qualified": False}, enabled=True) is True


def test_should_prune_fix_qualified_true_keeps_even_if_file_match_false(tmp_path):
    """KL-G3-2: pointed primer salah TAPI gold ada di candidate lain → JANGAN
    prune (FIX mengiterasi shortlist; signature 13033/13964)."""
    p = _write_gold_eval(tmp_path, file_match=False, qualified=True)
    assert should_prune_fix(p, enabled=True) is False
    assert should_prune_fix({"file_match": False, "qualified": True}, enabled=True) is False


def test_should_prune_fix_localize_hit_keeps(tmp_path):
    """localize benar (file_match=true, qualified=true) → jangan prune."""
    p = _write_gold_eval(tmp_path, file_match=True, qualified=True)
    assert should_prune_fix(p, enabled=True) is False


def test_should_prune_fix_none_or_missing_is_failsafe(tmp_path):
    """qualified None / field hilang / file tak ada → JANGAN prune (fail-safe).
    Termasuk gold_eval era-lama yang hanya punya file_match tanpa qualified."""
    p_none = _write_gold_eval(tmp_path)  # tanpa field sama sekali
    assert should_prune_fix(p_none, enabled=True) is False
    assert should_prune_fix({"qualified": None}, enabled=True) is False
    assert should_prune_fix({}, enabled=True) is False
    assert should_prune_fix({"file_match": False}, enabled=True) is False  # era-lama
    missing = tmp_path / "tidak-ada.json"
    assert should_prune_fix(missing, enabled=True) is False


# --- validasi dunia-nyata (read-only, artifacts nyata) ---------------------
# Dilewati kalau dir artifacts sudah tidak ada (repo bersih / dir dihapus).

_ARTIFACTS_LDEV = (Path(__file__).resolve().parent.parent.parent
                   / "artifacts" / "l-dev")


def test_should_prune_fix_real_localize_miss_13925():
    """django__django-13925 r1: qualified=false nyata (Kelas-A sejati) → prune True."""
    p = _ARTIFACTS_LDEV / "l-dev--django__django-13925--r1" / "gold_eval.json"
    if not p.is_file():
        import pytest
        pytest.skip("artifacts 13925 tidak ada")
    assert should_prune_fix(p, enabled=True) is True
    assert should_prune_fix(p, enabled=False) is False


def test_should_prune_fix_real_false_prune_13033_now_keeps():
    """django__django-13033 r1: file_match=false TAPI qualified=true (gold di
    candidate-2) → TIDAK di-prune lagi (regresi KH-17; dulu case ini di-skip
    salah dan terbukti solvable saat FIX diberi kesempatan)."""
    p = _ARTIFACTS_LDEV / "l-dev--django__django-13033--r1" / "gold_eval.json"
    if not p.is_file():
        import pytest
        pytest.skip("artifacts 13033 tidak ada")
    assert should_prune_fix(p, enabled=True) is False


def test_should_prune_fix_real_localize_hit_keeps():
    """Satu run l-dev dgn file_match=true → prune False (jalankan FIX)."""
    import pytest
    hit = None
    if _ARTIFACTS_LDEV.is_dir():
        for p in _ARTIFACTS_LDEV.glob("l-dev--*--r*/gold_eval.json"):
            try:
                if json.loads(p.read_text(encoding="utf-8")).get("file_match") is True:
                    hit = p
                    break
            except Exception:
                continue
    if hit is None:
        pytest.skip("tak ada run l-dev dgn file_match=true")
    assert should_prune_fix(hit, enabled=True) is False
