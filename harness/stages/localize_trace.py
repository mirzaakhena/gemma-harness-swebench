"""Lever L#3 (trace-injection) — sisi host: jalankan trace run, parse pool,
format injeksi pesan user, subset check candidates ⊆ pool.

Latar (VERDICT L#2, vault R-dev Log): kelas eksplorasi/framing (11964,
11797) kebal rule pasif & enumerasi mekanis — file akar tak pernah masuk
bidang pandang model. Obatnya injeksi sinyal eksternal: harness eksekusi
repro.py di container SEGAR di bawah coverage trace (localize_tracer.py),
himpunan file repo yang tereksekusi diinject sebagai kandidat pool, dan
candidates.md di-enforce ⊆ pool. Rasional: akar yang tak tereksekusi saat
repro ≈ kontradiksi dengan repro yang flip-able. Base-world murni, nol gold.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

TRACE_SENTINEL = "===TRACE_POOL==="
POOL_HEADER = "FILES EXECUTED DURING REPRODUCTION"


def parse_trace_output(raw: str) -> list[str]:
    """Ambil pool dari stdout trace run; ValueError bila trace tak sehat.

    Pool kosong ditolak: tanpa file repo yang tersaksikan, lever jadi
    no-op senyap — lebih baik gagal keras (kelas no-silent-caps).
    """
    if TRACE_SENTINEL not in raw:
        raise ValueError(
            f"trace output has no sentinel {TRACE_SENTINEL!r}; "
            f"tail: {raw[-500:]!r}")
    payload = raw.split(TRACE_SENTINEL, 1)[1].strip()
    try:
        pool = json.loads(payload)
    except json.JSONDecodeError as e:
        raise ValueError(f"trace pool is not valid JSON: {e}") from e
    if not isinstance(pool, list) or not all(isinstance(p, str) for p in pool):
        raise ValueError(f"trace pool must be a list of paths, got: {pool!r}")
    if not pool:
        raise ValueError("trace pool is empty — repro executed no repo file")
    return sorted(set(pool))


def format_trace_pool_message(pool: list[str]) -> str:
    """Blok English untuk pesan user pertama driver LOCALIZE."""
    listing = "\n".join(pool)
    return (
        f"{POOL_HEADER} — every repository file that ran while "
        "/testbed/.pipe/repro.py reproduced the bug. The root cause executed "
        "during reproduction, so it is one of these files. Choose your "
        "candidates from this list:\n" + listing)


def candidates_pool_error(candidate_files: list[str],
                          pool: set[str]) -> str | None:
    """Feedback English penahan DONE bila ada kandidat di luar pool."""
    outside = [f for f in candidate_files if f.lstrip("/") not in pool]
    if not outside:
        return None
    listing = ", ".join(repr(f) for f in outside)
    return (f"Not done yet: candidate file(s) {listing} did not execute "
            f"while reproducing the bug — choose your candidates from the "
            f"{POOL_HEADER} list you were given.")


def run_trace(image: str, files_host_dir: str,
              timeout: int = 300) -> tuple[list[str], str]:
    """Eksekusi repro.py di container segar di bawah tracer.

    files_host_dir = dir input REPRODUCE (repro.py + pipe_runtime.py bila
    ada) — pola mount sama dengan repro_sandbox_runner. Return (pool,
    output_mentah); ValueError bila pool tak sehat (dibiarkan naik —
    lever wajib hidup, bukan fail-open senyap).
    """
    tracer_dir = str(Path(__file__).resolve().parent)
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{files_host_dir}:/pipe-in:ro",
        "-v", f"{tracer_dir}:/tracer-in:ro",
        image,
        "bash", "-lc",
        "mkdir -p /testbed/.pipe && cp /pipe-in/repro.py /testbed/.pipe/repro.py "
        "&& { [ -f /pipe-in/pipe_runtime.py ] "
        "&& cp /pipe-in/pipe_runtime.py /testbed/.pipe/pipe_runtime.py; true; } "
        "&& cd /testbed "
        "&& python /tracer-in/localize_tracer.py /testbed/.pipe/repro.py 2>&1; "
        f"echo '{TRACE_SENTINEL}'; cat /tmp/trace_pool.json",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    raw = (p.stdout or "") + (p.stderr or "")
    return parse_trace_output(raw), raw
