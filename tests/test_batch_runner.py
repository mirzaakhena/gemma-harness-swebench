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
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_rlfv_batch  # noqa: E402
from run_rlfv_batch import (  # noqa: E402
    dedup_results,
    next_free_rerun,
    next_launchable,
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


# --- next_launchable (scheduler murni mode --parallel) ----------------------
# Invarian anti slot-race: `next_free_rerun` membaca direktori SAAT START; dua
# draw same-case yang start simultan bisa memilih nomor rerun yang SAMA →
# tabrakan run dir = korupsi (append-only mutlak, lihat insiden 2026-07-20).
# Maka duplikat di antrean (multi-draw, mis. A,A,A,B,B) harus SERIAL per case
# tapi boleh paralel lintas case.

def test_next_launchable_same_case_blocked_while_active():
    """Item same-case tidak launchable saat case itu aktif; item beda case
    launchable (paralel lintas case, serial per case)."""
    queue = ["django__django-1", "django__django-1", "astropy__astropy-2"]
    # django-1 sedang aktif di lane lain → draw kedua django-1 dilewati,
    # astropy-2 (indeks 2) yang boleh diluncurkan
    assert next_launchable(queue, {"django__django-1"}) == 2
    # tak ada yang aktif → item paling awal
    assert next_launchable(queue, set()) == 0


def test_next_launchable_respects_queue_order():
    """Kandidat paling AWAL yang boleh — urutan antrean dihormati."""
    assert next_launchable(["b", "a", "c"], set()) == 0
    # b aktif → kandidat paling awal berikutnya adalah a (indeks 1), bukan c
    assert next_launchable(["b", "a", "c"], {"b"}) == 1


def test_next_launchable_empty_or_all_active_returns_none():
    assert next_launchable([], set()) is None
    assert next_launchable([], {"a"}) is None
    assert next_launchable(["a", "a"], {"a"}) is None
    assert next_launchable(["a", "b"], {"a", "b"}) is None


# --- run_pool (mode --parallel N, rolling pool) -----------------------------
# Integrasi ringan: run_case dipalsukan (tanpa docker/GPU), N=2. Yang
# dibuktikan: (a) tak pernah ada 2 draw same-case aktif bersamaan, (b) semua
# item antrean dieksekusi, (c) results lengkap tersimpan di state, (d) tiap
# lane submit ala allow_concurrent=True (gate GPU akan deadlock antar-lane).

def test_run_pool_all_draws_executed_same_case_never_concurrent(tmp_path, monkeypatch):
    lock = threading.Lock()
    active_now: set = set()
    peak = [0]
    violations: list = []
    calls: list = []

    def fake_run_case(state_path, case, allow_concurrent=False,
                      prune_localize_miss=False, **kwargs):
        with lock:
            if case in active_now:
                violations.append(case)  # slot-race: dua draw same-case aktif
            active_now.add(case)
            peak[0] = max(peak[0], len(active_now))
            calls.append((case, allow_concurrent))
        time.sleep(0.02)  # beri kesempatan lane lain tumpang tindih
        with lock:
            active_now.discard(case)
        return {"case": case, "swebench_eval": {"resolved": True}}

    monkeypatch.setattr(run_rlfv_batch, "run_case", fake_run_case)
    state = tmp_path / "batch-state.json"
    results: list = []
    queue = ["A", "A", "A", "B", "B", "C"]  # 3 draw A + 2 draw B + 1 draw C
    run_rlfv_batch.run_pool(state, queue, parallel=2, results=results)

    assert violations == []  # invarian same-case-serial tak pernah dilanggar
    assert sorted(c for c, _ in calls) == sorted(queue)  # semua draw jalan
    assert all(ac is True for _, ac in calls)  # pool bypass gate GPU
    assert peak[0] <= 2  # tak pernah melebihi N lane
    saved = json.loads(state.read_text(encoding="utf-8"))["results"]
    assert len(saved) == len(queue)
    assert all("finished" in r for r in saved)  # format entri sama dgn serial


def test_run_pool_exception_in_one_lane_does_not_kill_pool(tmp_path, monkeypatch):
    """Satu draw meledak → dicatat sebagai error (semantik loop serial),
    draw lain tetap dieksekusi sampai antrean habis. Entri lama di results
    (resume) tidak boleh hilang dari state."""
    def fake_run_case(state_path, case, allow_concurrent=False,
                      prune_localize_miss=False, **kwargs):
        if case == "BOOM":
            raise RuntimeError("meledak di lane")
        return {"case": case, "swebench_eval": {"resolved": True}}

    monkeypatch.setattr(run_rlfv_batch, "run_case", fake_run_case)
    state = tmp_path / "batch-state.json"
    results: list = [{"case": "LAMA", "swebench_eval": {"resolved": False},
                      "finished": "2026-07-21T00:00:00+00:00"}]
    run_rlfv_batch.run_pool(state, ["BOOM", "A", "B"], parallel=2,
                            results=results)

    assert len(results) == 4  # 1 lama + 3 draw
    boom = next(r for r in results if r["case"] == "BOOM")
    assert "exception" in boom["error"]
    saved = json.loads(state.read_text(encoding="utf-8"))["results"]
    assert len(saved) == 4
    assert saved[0]["case"] == "LAMA"  # entri resume tetap di depan


# --- case_paths ------------------------------------------------------------
# Insiden 2026-07-22 (Mac): path problem/gold di run_case hardcode backslash
# Windows ("cases\\problems\\...") -> di POSIX jadi nama file literal ->
# FileNotFoundError, driver FIX crash 0 detik dan slot rerun hangus (r6/r6/r7
# 11910/15388/12184). Path WAJIB dibangun via pathlib agar portabel.

def test_case_paths_portable_no_backslash_on_posix():
    prob, gold = run_rlfv_batch.case_paths("django__django-11910")
    import os
    if os.sep == "/":
        assert "\\" not in prob and "\\" not in gold
    assert prob == str(Path("cases") / "problems" / "django__django-11910.txt")
    assert gold == str(Path("cases") / "gold" / "django__django-11910" / "gold.patch")


# --- void-infra & cap MAX_RERUN (KH-22) ------------------------------------
# Insiden 2026-07-22: 15902/14855 punya 5-6 run "bangkai" (driver crash
# endpoint mati, 0 turn model) yang tervonis repro-missing biasa -> cap
# `next_free_rerun > MAX_RERUN` menghitung bangkai sebagai percobaan dan
# menolak retest sah ("BERHENTI setelah 0 rerun" pada 14855 r10).

def _mk_void_run(tmp_path, name, events_text=None, infra_abort=False):
    d = tmp_path / name
    d.mkdir(parents=True)
    if events_text is not None:
        (d / "events.jsonl").write_text(events_text, encoding="utf-8")
    if infra_abort:
        (d / "infra_abort.json").write_text('{"reason": "preflight"}', encoding="utf-8")
    return d

def test_void_infra_run_marker_file_wins():
    import tempfile
    from pathlib import Path as P
    with tempfile.TemporaryDirectory() as t:
        d = _mk_void_run(P(t), "r-dev--c--r1", events_text='{"type":"enter"}\n', infra_abort=True)
        assert run_rlfv_batch.is_void_infra_run(d) is True

def test_void_infra_run_legacy_crash_no_model_signal():
    import tempfile
    from pathlib import Path as P
    with tempfile.TemporaryDirectory() as t:
        ev = ('{"type":"enter"}\n'
              '{"type":"abort","detail":{"reason":"driver crash: URLError(TimeoutError(10060))"}}\n'
              '{"type":"exit"}\n')
        d = _mk_void_run(P(t), "r-dev--c--r1", events_text=ev)
        assert run_rlfv_batch.is_void_infra_run(d) is True

def test_void_infra_run_real_attempt_with_model_signal_not_void():
    import tempfile
    from pathlib import Path as P
    with tempfile.TemporaryDirectory() as t:
        ev = ('{"type":"enter"}\n'
              '{"type":"retry","detail":{"why":"x"},"budget":{"msg_used":7}}\n'
              '{"type":"abort","detail":{"reason":"driver crash: URLError"}}\n')
        d = _mk_void_run(P(t), "r-dev--c--r1", events_text=ev)
        # ada sinyal model (msg_used) tapi crash -> legacy: TIDAK void (konservatif);
        # run era-baru sekelas ini akan ditandai infra_abort.json oleh driver.
        assert run_rlfv_batch.is_void_infra_run(d) is False

def test_void_infra_run_unreadable_counts_as_attempt():
    import tempfile
    from pathlib import Path as P
    with tempfile.TemporaryDirectory() as t:
        d = _mk_void_run(P(t), "r-dev--c--r1")  # tanpa events.jsonl
        assert run_rlfv_batch.is_void_infra_run(d) is False  # gagal-aman: hitung

def test_valid_rerun_attempts_excludes_void(tmp_path):
    camp = tmp_path
    ev_real = '{"type":"retry","budget":{"msg_used":3}}\n'
    ev_void = '{"type":"abort","detail":{"reason":"driver crash: URLError"}}\n'
    _mk_void_run(camp, "r-dev--case-a--r1", events_text=ev_real)
    _mk_void_run(camp, "r-dev--case-a--r2", events_text=ev_void)
    _mk_void_run(camp, "r-dev--case-a--r3", events_text=ev_void)
    _mk_void_run(camp, "r-dev--case-a--r4", infra_abort=True, events_text='{"type":"enter"}\n')
    _mk_void_run(camp, "r-dev--case-b--r1", events_text=ev_real)  # case lain: diabaikan
    assert run_rlfv_batch.valid_rerun_attempts(camp, "r-dev", "case-a") == 1
