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
import time
from datetime import datetime, timezone
from pathlib import Path

MAIN = Path(__file__).resolve().parent.parent
ARTIFACTS = MAIN.parent / "artifacts"
GPU_CHECK = Path(
    r"C:\Users\Mirza\workspace-shared\smartm2m-bench\swe\harness-uplift"
    r"\swebench-original\gpu_check.py"
)
IMAGE_TMPL = "ghcr.io/epoch-research/swe-bench.eval.x86_64.{case}:latest"
MAX_RERUN = 3
GPU_POLL_SECONDS = 10
GPU_POLL_MAX = 180  # 30 menit


# --------------------------------------------------------------------------
# util murni (diuji di tests/test_batch_runner.py)
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# eksekusi
# --------------------------------------------------------------------------

def log(state_path: Path, msg: str) -> None:
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    line = f"[{stamp}] {msg}"
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
             prune_localize_miss: bool = False) -> dict:
    """Jalankan R -> L -> F -> V untuk satu case. Kembalikan ringkasan."""
    img = IMAGE_TMPL.format(case=case)
    prob = f"cases\\problems\\{case}.txt"
    gold = f"cases\\gold\\{case}\\gold.patch"
    res: dict = {"case": case, "started": datetime.now(timezone.utc).astimezone().isoformat()}

    # --- REPRODUCE (rerun sampai qualified atau MAX_RERUN) ---
    rq = qualified_rerun(ARTIFACTS / "r-dev", "r-dev", case)
    attempts = 0
    while rq is None and attempts < MAX_RERUN:
        n = next_free_rerun(ARTIFACTS / "r-dev", "r-dev", case)
        if n > MAX_RERUN:
            log(state_path, f"  slot rerun R sudah melewati {MAX_RERUN}, berhenti")
            break
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
        n = next_free_rerun(ARTIFACTS / "l-dev", "l-dev", case)
        if n > MAX_RERUN:
            break
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
    for i, case in enumerate(cases, 1):
        if not args.no_resume and already_done(case):
            log(state_path, f"[{i}/{len(cases)}] {case} — SUDAH ADA swebench_eval, dilewati")
            continue
        log(state_path, f"[{i}/{len(cases)}] {case} — mulai")
        try:
            res = run_case(state_path, case, args.allow_concurrent,
                           args.prune_localize_miss)
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
    ok = sum(1 for r in results if (r.get("swebench_eval") or {}).get("resolved"))
    log(state_path, f"resolved={ok} dari {len(results)} case yang dijalankan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
