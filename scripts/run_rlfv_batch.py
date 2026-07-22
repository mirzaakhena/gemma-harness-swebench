r"""Batch runner RLFV — jalankan pipeline penuh untuk banyak case, serial, tanpa ditunggui.

Dibuat 2026-07-20 (bot-01) untuk run semalaman. Menggantikan orkestrasi manual
per-case yang sebelumnya dilakukan subagent, dan menutup tiga jebakan yang sudah
memakan korban:

1. **Cap tool 10 menit.** Subagent yang membungkus driver dalam satu panggilan tool
   kena kill di tengah run (fase REPRODUCE bisa 18+ menit). Script ini dijalankan
   sebagai proses OS sendiri, jadi tidak terikat cap itu.
2. **Rename run dir.** Pernah terjadi: run parsial di-rename agar slot r1 bebas,
   yang memecah konsistensi antara nama folder, run_id di events.jsonl, dan
   runs.jsonl. Script ini TIDAK PERNAH me-rename/menghapus apa pun — ia memilih
   nomor rerun bebas berikutnya.
3. **Tabrakan GPU.** vLLM dipakai bersama. Sebelum tiap pemanggilan Gemma, script
   menunggu `waiting == 0` DAN tidak ada container `gemma-work-*` milik case lain.

Pemakaian (dari root main\):

    python scripts\run_rlfv_batch.py --cases cases.txt --state ..\artifacts\batch-state.json

`--cases` menerima file berisi satu case id per baris (baris kosong dan yang
diawali `#` diabaikan), atau daftar dipisah koma lewat `--case-list`.

Aman diulang: state disimpan per case, dan `--resume` (default) melewati case yang
sudah punya `swebench_eval.json`. Jadi kalau mati di tengah, jalankan ulang saja.

Mode pool (2026-07-22): `--parallel N` menjalankan rolling pool N lane thread
dalam SATU proses — selalu ada N draw aktif; begitu satu selesai, slotnya
langsung diisi dari antrean (`next_launchable`). Invarian same-case-serial: dua
draw untuk case yang SAMA tak pernah aktif bersamaan, karena `next_free_rerun`
membaca direktori saat start — dua start simultan bisa memilih nomor rerun yang
sama, dan tabrakan run dir = korupsi (append-only mutlak). Duplikat di antrean
sah (mis. A,A,A,B,B = 3 draw A + 2 draw B): serial per case, paralel lintas
case. Tiap lane submit langsung ke Gemma (bypass gate ala --allow-concurrent):
endpoint eksklusif milik kita, gate `waiting==0` + cek container case lain akan
deadlock antar-lane. N=1 (default) = jalur serial lama, tidak berubah.

Yang TIDAK dilakukan script ini, sengaja: autopsi katalog lever, commit, dan
pelaporan ke user. Itu tugas bot yang menjalankannya (lihat docs/sop-rlfv-case-run.md
§5-§7).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue

MAIN = Path(__file__).resolve().parent.parent
ARTIFACTS = MAIN.parent / "artifacts"
# 2026-07-22: skrip Windows lama (C:\...\swebench-original\gpu_check.py) tidak
# ikut ke mesin ini; direkonstruksi lintas-platform di scripts/gpu_check.py
# (kontrak output sama — baris terakhir `vLLM queue: {...}`).
GPU_CHECK = Path(__file__).resolve().parent / "gpu_check.py"
IMAGE_TMPL = "ghcr.io/epoch-research/swe-bench.eval.x86_64.{case}:latest"
MAX_RERUN = 3
GPU_POLL_SECONDS = 10
GPU_POLL_MAX = 180  # 30 menit


# --------------------------------------------------------------------------
# util murni (diuji di tests/test_batch_runner.py)
# --------------------------------------------------------------------------

def case_paths(case: str) -> tuple[str, str]:
    """Path problem-file & gold-patch, portabel lintas-OS (relatif thd MAIN).

    2026-07-22 (Mac): versi lama hardcode backslash Windows
    (f"cases\\\\problems\\\\{case}.txt") -> di POSIX jadi nama file literal ->
    FileNotFoundError, driver FIX crash 0 detik, slot rerun hangus."""
    prob = str(Path("cases") / "problems" / f"{case}.txt")
    gold = str(Path("cases") / "gold" / case / "gold.patch")
    return prob, gold


def parse_case_list(text: str) -> list[str]:
    """Baris kosong dan komentar '#' diabaikan; sisanya di-strip."""
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def parse_waiting(gpu_output: str) -> int | None:
    """Ambil angka `waiting` dari baris `vLLM queue: {'running': N, 'waiting': M}`.

    None berarti tidak terbaca — pemanggil WAJIB memperlakukannya sebagai sibuk,
    bukan sebagai nol. Gagal-aman ke arah menunggu.
    """
    m = re.search(r"'waiting'\s*:\s*(\d+)", gpu_output)
    return int(m.group(1)) if m else None


def next_free_rerun(campaign_dir: Path, campaign: str, case: str) -> int:
    """Nomor rerun bebas berikutnya. TIDAK PERNAH memakai ulang slot terpakai."""
    n = 1
    while (campaign_dir / f"{campaign}--{case}--r{n}").exists():
        n += 1
    return n


def should_prune_fix(gold_eval, enabled: bool) -> bool:
    """Keputusan ORKESTRASI (bukan gate produk): haruskah FIX di-SKIP karena
    LOCALIZE sudah pasti meleset dari gold?

    PENTING soal prinsip: ini dipakai HANYA di batch runner (orkestrasi dev),
    yang MEMANG boleh memegang gold DI LUAR loop model. Pipeline produk
    REPRODUCE->LOCALIZE->FIX tetap gold-blind — model tak pernah melihat gold,
    dan gate LOCALIZE produk (harness/stages/run_localize_gates.py) tidak
    membaca file ini. Tujuannya murni hemat compute dev: kalau
    `localize_gold_eval` sudah menuliskan bahwa file yang di-localize BUKAN file
    gold, menjalankan FIX hanya membuang GPU pada case yang end-to-end pasti
    gagal. Case yang di-skip TETAP dihitung gagal di papan skor (tidak resolved).
    Ini BUKAN membocorkan gold ke model.

    Argumen `gold_eval` boleh berupa path ke `gold_eval.json` (l-dev run dir)
    atau dict yang sudah di-parse. Kembalikan True HANYA saat `enabled` dan
    `qualified` eksplisit False — BUKAN `file_match` (KL-G3-2/KH-17): FIX
    mengiterasi SELURUH shortlist, jadi selama gold ada di salah satu kandidat
    (`qualified=true`) FIX masih bisa menang walau pointed primer meleset
    (terbukti: 13033 di-prune atas file_match lalu resolved=true saat re-run).
    Semua kondisi lain (flag off, file hilang / tak terbaca, `qualified`
    None/tak ada — termasuk gold_eval era-lama tanpa field ini) → False =
    GAGAL-AMAN (tetap jalankan FIX)."""
    if not enabled:
        return False
    data = gold_eval
    if not isinstance(data, dict):
        try:
            data = json.loads(Path(gold_eval).read_text(encoding="utf-8"))
        except Exception:
            return False  # tak terbaca → jangan prune (fail-safe)
    return data.get("qualified") is False


def is_void_infra_run(run_dir: Path) -> bool:
    """Run "bangkai" infra (KH-22): driver crash pra/ekstra-model sehingga run
    tak membawa sinyal model — TIDAK boleh dihitung sebagai percobaan.

    Aturan (konservatif, gagal-aman ke arah MENGHITUNG sebagai percobaan):
    1. `infra_abort.json` ada (ditulis driver era-baru) → void.
    2. Legacy (pra-label): events.jsonl memuat abort 'driver crash' DAN tidak
       ada satu pun sinyal model (`msg_used`) → void. Ada sinyal model → BUKAN
       void (mis. 14855 r7: 21 turn lalu crash — era-baru akan berlabel
       infra_abort.json; legacy dihitung percobaan, konservatif).
    3. events.jsonl tak ada/tak terbaca → BUKAN void (hitung; jangan beri
       retry gratis atas dir misterius)."""
    if (run_dir / "infra_abort.json").is_file():
        return True
    try:
        text = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    except Exception:
        return False
    return ("driver crash" in text) and ("msg_used" not in text)


def valid_rerun_attempts(campaign_dir: Path, campaign: str, case: str) -> int:
    """Jumlah percobaan SAH (non-void) sebuah case di kampanye — pengganti
    proxy lama `next_free_rerun > MAX_RERUN` yang menghitung bangkai infra
    (insiden 14855 r10: 6 bangkai memblokir retest sah)."""
    n = 0
    for p in campaign_dir.glob(f"{campaign}--{case}--r*"):
        if re.search(r"--r(\d+)$", p.name) and not is_void_infra_run(p):
            n += 1
    return n


def qualified_rerun(campaign_dir: Path, campaign: str, case: str) -> int | None:
    """Nomor rerun QUALIFIED terakhir (pass_l1 true), bukan nomor terbesar."""
    best = None
    for p in campaign_dir.glob(f"{campaign}--{case}--r*"):
        m = re.search(r"--r(\d+)$", p.name)
        if not m:
            continue
        try:
            v = json.loads((p / "verdict.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        if v.get("pass_l1"):
            n = int(m.group(1))
            best = n if best is None else max(best, n)
    return best


def next_launchable(queue, active_cases) -> int | None:
    """Scheduler murni mode pool: indeks item antrean paling AWAL yang case-nya
    tidak sedang aktif; None bila tak ada yang boleh diluncurkan.

    Invarian anti slot-race: dua draw untuk case yang SAMA tak boleh aktif
    bersamaan — `next_free_rerun` membaca direktori saat start, dua start
    simultan bisa memilih nomor rerun yang sama (append-only mutlak; tabrakan
    run dir = korupsi). Duplikat di antrean sah (multi-draw, mis. A,A,A,B,B):
    serial per case, paralel lintas case."""
    for i, case in enumerate(queue):
        if case not in active_cases:
            return i
    return None


def dedup_results(results):
    """R6: papan skor batch tahan-resume. State di-append lintas resume
    (main() :350-370), jadi satu `case` bisa muncul >1 kali di list akumulasi
    (mis. crash lalu jalankan ulang). Kembalikan satu entri per case supaya
    ringkasan (:379-380) tak menggelembung. Entri TERAKHIR yang di-append untuk
    sebuah case yang menang (paling mutakhir/lengkap); urutan mengikuti
    kemunculan-pertama tiap case. Semantik prune tak berubah: case self-pruned
    tetap tanpa `swebench_eval` → tetap dihitung gagal oleh pemanggil."""
    deduped: dict = {}
    for r in results:
        deduped[r.get("case")] = r
    return list(deduped.values())


# --------------------------------------------------------------------------
# eksekusi
# --------------------------------------------------------------------------

# Mode pool berjalan multi-thread: log dan state/results dilindungi lock
# terpisah supaya baris log tak saling menyisip dan state tak korup. Di mode
# serial lock ini tak pernah kontensi (no-op praktis).
_LOG_LOCK = threading.Lock()
_STATE_LOCK = threading.Lock()
_LOG_CTX = threading.local()  # per-thread: prefiks "[lane-N] " utk keterbacaan


def log(state_path: Path, msg: str) -> None:
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    prefix = getattr(_LOG_CTX, "prefix", "")
    line = f"[{stamp}] {prefix}{msg}"
    with _LOG_LOCK:
        print(line, flush=True)
        with open(state_path.with_suffix(".log"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def run(cmd: list[str], cwd: Path = MAIN) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def gemma_containers_for_other_cases(case: str) -> list[str]:
    _, out = run(["docker", "ps", "--format", "{{.Names}}"])
    names = [n.strip() for n in out.splitlines() if n.strip().startswith("gemma-work")]
    return [n for n in names if case.replace("__", "-") not in n and case not in n]


def wait_for_gpu(state_path: Path, case: str,
                 allow_concurrent: bool = False) -> bool:
    """Tunggu sampai antrean vLLM kosong DAN tidak ada run Gemma case lain.

    allow_concurrent=True (EKSPERIMEN throughput paralel): BYPASS TOTAL —
    submit langsung tanpa menunggu gate `waiting==0` maupun cek container
    case lain. Tujuannya menguji apakah continuous-batching vLLM memberi
    throughput lebih tinggi saat beberapa pipeline slam server bersamaan.
    Konsekuensi (dibahas & diterima Mirza 2026-07-21): bisa menaikkan
    `waiting` server bersama."""
    if allow_concurrent:
        log(state_path, "  [gpu] allow_concurrent: bypass gate, submit langsung")
        return True
    for i in range(GPU_POLL_MAX):
        code, out = run([sys.executable, str(GPU_CHECK)])
        waiting = parse_waiting(out)
        others = gemma_containers_for_other_cases(case)
        if waiting == 0 and not others:
            return True
        why = f"waiting={waiting}" if waiting != 0 else f"container lain: {others}"
        if i % 6 == 0:
            log(state_path, f"  [gpu] menunggu ({why})")
        time.sleep(GPU_POLL_SECONDS)
    log(state_path, "  [gpu] MENYERAH setelah batas tunggu")
    return False


def stage(state_path: Path, label: str, cmd: list[str]) -> tuple[int, str]:
    log(state_path, f"  -> {label}")
    t0 = time.time()
    code, out = run(cmd)
    log(state_path, f"  <- {label} exit={code} ({time.time() - t0:.0f}s)")
    if code != 0:
        tail = "\n".join(out.strip().splitlines()[-5:])
        log(state_path, f"     stderr/stdout tail: {tail}")
    return code, out


def already_done(case: str) -> bool:
    for p in (ARTIFACTS / "f-dev").glob(f"f-dev--{case}--r*"):
        if (p / "swebench_eval.json").is_file():
            return True
    return False


def run_case(state_path: Path, case: str,
             allow_concurrent: bool = False,
             prune_localize_miss: bool = False,
             max_rerun: int = MAX_RERUN) -> dict:
    """Jalankan R -> L -> F -> V untuk satu case. Kembalikan ringkasan."""
    img = IMAGE_TMPL.format(case=case)
    prob, gold = case_paths(case)
    res: dict = {"case": case, "started": datetime.now(timezone.utc).astimezone().isoformat()}

    # --- REPRODUCE (rerun sampai qualified atau MAX_RERUN) ---
    rq = qualified_rerun(ARTIFACTS / "r-dev", "r-dev", case)
    attempts = 0
    while rq is None and attempts < MAX_RERUN:
        # KH-22: cap = jumlah percobaan SAH (non-void), bukan nomor slot —
        # bangkai infra (driver-crash 0-turn) tidak memblokir retest sah.
        if valid_rerun_attempts(ARTIFACTS / "r-dev", "r-dev", case) >= max_rerun:
            log(state_path, f"  percobaan R valid sudah >= {max_rerun}, berhenti")
            break
        n = next_free_rerun(ARTIFACTS / "r-dev", "r-dev", case)
        if not wait_for_gpu(state_path, case, allow_concurrent):
            res["error"] = "gpu-timeout-reproduce"
            return res
        stage(state_path, f"REPRODUCE r{n}", [
            sys.executable, "-m", "harness.stages.run_reproduce_gemma",
            "--case", case, "--rerun", str(n), "--image", img,
            "--problem-file", prob])
        stage(state_path, f"repro_gates r{n}", [
            sys.executable, "-m", "harness.stages.run_repro_gates",
            "--case", case, "--rerun", str(n), "--image", img, "--gold", gold])
        rq = qualified_rerun(ARTIFACTS / "r-dev", "r-dev", case)
        attempts += 1
    if rq is None:
        res["error"] = "reproduce-not-qualified"
        log(state_path, f"  BERHENTI: REPRODUCE tidak qualified setelah {attempts} rerun")
        return res
    res["r_qualified"] = rq
    r_files = str(ARTIFACTS / "r-dev" / f"r-dev--{case}--r{rq}" / "files")

    # --- LOCALIZE ---
    lq = qualified_rerun(ARTIFACTS / "l-dev", "l-dev", case)
    attempts = 0
    while lq is None and attempts < MAX_RERUN:
        if valid_rerun_attempts(ARTIFACTS / "l-dev", "l-dev", case) >= max_rerun:
            log(state_path, f"  percobaan L valid sudah >= {max_rerun}, berhenti")
            break
        n = next_free_rerun(ARTIFACTS / "l-dev", "l-dev", case)
        if not wait_for_gpu(state_path, case, allow_concurrent):
            res["error"] = "gpu-timeout-localize"
            return res
        stage(state_path, f"LOCALIZE r{n}", [
            sys.executable, "-m", "harness.stages.run_localize_gemma",
            "--case", case, "--rerun", str(n), "--image", img,
            "--input-files", r_files, "--problem-file", prob])
        stage(state_path, f"localize_gates r{n}", [
            sys.executable, "-m", "harness.stages.run_localize_gates",
            "--case", case, "--rerun", str(n), "--image", img])
        stage(state_path, f"localize_gold_eval r{n}", [
            sys.executable, "-m", "eval.localize_gold_eval",
            "--case", case, "--rerun", str(n), "--gold", gold])
        lq = qualified_rerun(ARTIFACTS / "l-dev", "l-dev", case)
        attempts += 1
    if lq is None:
        res["error"] = "localize-not-qualified"
        log(state_path, "  BERHENTI: LOCALIZE tidak qualified")
        return res
    res["l_qualified"] = lq
    l_files = str(ARTIFACTS / "l-dev" / f"l-dev--{case}--r{lq}" / "files")
    if not (Path(l_files) / "candidates.md").is_file():
        res["error"] = "localize-tanpa-candidates.md"
        log(state_path, "  BERHENTI: run L qualified tidak punya candidates.md")
        return res

    # --- PRUNE ORKESTRASI (opsional, --prune-localize-miss) ---
    # Keputusan hemat-compute DI LUAR loop model: batch runner (bukan gate
    # produk) membaca gold_eval.json LOCALIZE dan, bila file yang di-localize
    # BUKAN file gold (file_match=false), melewati FIX/VERIFY. Pipeline produk
    # tetap gold-blind; gate LOCALIZE produk tak tersentuh; case ini TETAP
    # dihitung gagal (tidak resolved) di papan skor end-to-end. Gagal-aman:
    # kalau gold_eval.json tak ada/tak terbaca/file_match None → tetap FIX.
    l_gold_eval = ARTIFACTS / "l-dev" / f"l-dev--{case}--r{lq}" / "gold_eval.json"
    if should_prune_fix(l_gold_eval, prune_localize_miss):
        res["error"] = "skipped-fix-localize-miss"
        res["localize_gold_miss"] = True
        log(state_path,
            "  SKIP FIX: localize meleset gold (file_match=false) — hemat compute")
        return res

    # --- FIX + VERIFY ---
    fn = next_free_rerun(ARTIFACTS / "f-dev", "f-dev", case)
    if not wait_for_gpu(state_path, case, allow_concurrent):
        res["error"] = "gpu-timeout-fix"
        return res
    stage(state_path, f"FIX r{fn}", [
        sys.executable, "-m", "harness.stages.run_fix_gemma",
        "--case", case, "--rerun", str(fn), "--image", img,
        "--input-localize-files", l_files, "--input-repro-files", r_files,
        "--problem-file", prob])
    stage(state_path, f"fix_gates r{fn}", [
        sys.executable, "-m", "harness.stages.run_fix_gates",
        "--case", case, "--rerun", str(fn), "--image", img,
        "--input-repro-files", r_files])
    _, out = stage(state_path, f"swebench_checker r{fn}", [
        sys.executable, "-m", "eval.swebench_checker",
        "--case", case, "--rerun", str(fn)])
    stage(state_path, f"fix_gold_eval r{fn}", [
        sys.executable, "-m", "eval.fix_gold_eval",
        "--case", case, "--rerun", str(fn), "--gold", gold])
    res["f_rerun"] = fn

    for key, path in (("verdict", ARTIFACTS / "f-dev" / f"f-dev--{case}--r{fn}" / "verdict.json"),
                      ("swebench_eval", ARTIFACTS / "f-dev" / f"f-dev--{case}--r{fn}" / "swebench_eval.json"),
                      ("gold_eval", ARTIFACTS / "f-dev" / f"f-dev--{case}--r{fn}" / "gold_eval.json")):
        try:
            res[key] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            res[key] = None
    return res


def run_pool(state_path: Path, queue: list[str], parallel: int,
             results: list, prune_localize_miss: bool = False,
             max_rerun: int = MAX_RERUN) -> None:
    """Jalankan antrean draw dengan rolling pool `parallel` lane (threading).

    Selalu ada <=N draw aktif; begitu satu selesai, slot langsung diisi item
    launchable berikutnya (`next_launchable` — same-case tetap serial, lihat
    docstring modul). Tiap lane submit langsung ke Gemma
    (allow_concurrent=True): endpoint eksklusif milik kita, gate `waiting==0`
    + cek container case lain akan deadlock antar-lane. Exception satu lane
    TIDAK mematikan pool (ditangkap per draw, sama seperti loop serial).
    Hasil tiap draw di-append ke `results` + ditulis ke state di bawah
    _STATE_LOCK, format persis mode serial."""
    total = len(queue)
    pending = list(queue)
    done_q: Queue = Queue()  # lane id yang selesai, diisi worker
    active: dict[int, tuple[threading.Thread, str]] = {}
    free_lanes = list(range(1, parallel + 1))
    launched = 0

    log(state_path,
        f"mode pool: {parallel} lane, {total} draw — tiap lane BYPASS gate GPU "
        f"(allow_concurrent; endpoint eksklusif, gate akan deadlock antar-lane)")

    def lane_worker(lane: int, case: str, no: int) -> None:
        _LOG_CTX.prefix = f"[lane-{lane}] "
        log(state_path, f"[{no}/{total}] {case} — mulai")
        try:
            res = run_case(state_path, case, allow_concurrent=True,
                           prune_localize_miss=prune_localize_miss,
                           max_rerun=max_rerun)
        except Exception as exc:  # noqa: BLE001 — pool tidak boleh mati karena satu draw
            res = {"case": case, "error": f"exception: {exc!r}"}
            log(state_path, f"  EXCEPTION: {exc!r}")
        res["finished"] = datetime.now(timezone.utc).astimezone().isoformat()
        with _STATE_LOCK:
            results.append(res)
            state_path.write_text(
                json.dumps({"results": results}, ensure_ascii=False, indent=1),
                encoding="utf-8")
        sw = res.get("swebench_eval") or {}
        log(state_path, f"[{no}/{total}] {case} — selesai: "
                        f"resolved={sw.get('resolved')} error={res.get('error')}")
        done_q.put(lane)

    while pending or active:
        # isi semua lane kosong dengan item launchable paling awal
        while free_lanes:
            active_cases = {c for _, c in active.values()}
            idx = next_launchable(pending, active_cases)
            if idx is None:
                break
            case = pending.pop(idx)
            lane = free_lanes.pop(0)
            launched += 1
            t = threading.Thread(target=lane_worker, name=f"lane-{lane}",
                                 args=(lane, case, launched))
            active[lane] = (t, case)
            t.start()
        if not active:
            break  # defensif: mustahil selama pending hanya berisi case valid
        lane = done_q.get()  # blokir sampai ada lane selesai → slot diisi lagi
        t, _case = active.pop(lane)
        t.join()
        free_lanes.append(lane)
        free_lanes.sort()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cases", help="file berisi satu case id per baris")
    ap.add_argument("--case-list", help="daftar case dipisah koma")
    ap.add_argument("--state", default=str(ARTIFACTS / "batch-state.json"))
    ap.add_argument("--no-resume", action="store_true",
                    help="jangan lewati case yang sudah punya swebench_eval.json")
    ap.add_argument("--allow-concurrent", action="store_true",
                    help="EKSPERIMEN: lewati cek container Gemma case lain "
                         "supaya beberapa proses batch bisa jalan paralel "
                         "(gate waiting==0 tetap dijaga)")
    ap.add_argument("--parallel", type=int, default=1,
                    help="jumlah lane rolling pool dalam SATU proses (default "
                         "1 = serial lama, jalur kode tak berubah). N>=2: "
                         "N draw aktif sekaligus via thread; same-case tetap "
                         "serial (invarian next_free_rerun); tiap lane bypass "
                         "gate GPU ala --allow-concurrent.")
    ap.add_argument("--max-rerun", type=int, default=MAX_RERUN,
                    help="cap percobaan SAH (non-void) per fase per case "
                         "(default 3). Naikkan HANYA utk retest yang disetujui "
                         "eksplisit (mis. case dgn percobaan valid historis "
                         "banyak). Bangkai infra tak pernah dihitung (KH-22).")
    ap.add_argument("--prune-localize-miss", action="store_true",
                    help="ORKESTRASI hemat-compute (default OFF): SKIP FIX bila "
                         "gold_eval.json LOCALIZE menandai file_match=false. "
                         "Pakai gold DI LUAR loop model (batch runner, bukan "
                         "gate produk); pipeline produk tetap gold-blind; case "
                         "di-skip tetap dihitung gagal di papan skor.")
    args = ap.parse_args(argv)

    if args.cases:
        cases = parse_case_list(Path(args.cases).read_text(encoding="utf-8"))
    elif args.case_list:
        cases = [c.strip() for c in args.case_list.split(",") if c.strip()]
    else:
        ap.error("wajib --cases atau --case-list")

    state_path = Path(args.state)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    results = []
    if state_path.is_file():
        try:
            results = json.loads(state_path.read_text(encoding="utf-8")).get("results", [])
        except Exception:
            results = []

    log(state_path, f"=== BATCH MULAI: {len(cases)} case ===")
    if args.parallel > 1:
        # Mode pool: resume/already_done dicek SEKALI di scheduling awal
        # (semantik sama dgn loop serial yang cek di awal tiap case).
        queue_run = []
        for i, case in enumerate(cases, 1):
            if not args.no_resume and already_done(case):
                log(state_path, f"[{i}/{len(cases)}] {case} — SUDAH ADA swebench_eval, dilewati")
                continue
            queue_run.append(case)
        run_pool(state_path, queue_run, args.parallel, results,
                 args.prune_localize_miss, args.max_rerun)
        # Jumlah draw per case DI-LOG sebelum ringkasan: dedup_results hanya
        # menyisakan entri terakhir per case (semantik lama, sengaja), jadi
        # info multi-draw harus tercatat di sini agar tak hilang.
        draws: dict[str, int] = {}
        for c in queue_run:
            draws[c] = draws.get(c, 0) + 1
        if draws:
            log(state_path, "draw per case: " +
                ", ".join(f"{c}={n}" for c, n in draws.items()))
    else:
        for i, case in enumerate(cases, 1):
            if not args.no_resume and already_done(case):
                log(state_path, f"[{i}/{len(cases)}] {case} — SUDAH ADA swebench_eval, dilewati")
                continue
            log(state_path, f"[{i}/{len(cases)}] {case} — mulai")
            try:
                res = run_case(state_path, case, args.allow_concurrent,
                               args.prune_localize_miss, args.max_rerun)
            except Exception as exc:  # noqa: BLE001 — batch tidak boleh mati karena satu case
                res = {"case": case, "error": f"exception: {exc!r}"}
                log(state_path, f"  EXCEPTION: {exc!r}")
            res["finished"] = datetime.now(timezone.utc).astimezone().isoformat()
            results.append(res)
            state_path.write_text(
                json.dumps({"results": results}, ensure_ascii=False, indent=1),
                encoding="utf-8")
            sw = res.get("swebench_eval") or {}
            log(state_path, f"[{i}/{len(cases)}] {case} — selesai: "
                            f"resolved={sw.get('resolved')} error={res.get('error')}")

    log(state_path, "=== BATCH SELESAI ===")
    board = dedup_results(results)  # R6: tiap case dihitung sekali lintas resume
    ok = sum(1 for r in board if (r.get("swebench_eval") or {}).get("resolved"))
    log(state_path, f"resolved={ok} dari {len(board)} case yang dijalankan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
