r"""gpu_check — rekonstruksi lintas-platform (2026-07-22, menggantikan skrip Windows
`C:\...\swebench-original\gpu_check.py` yang tidak ikut ke mesin ini).

Dua sumber data:
1. `http://10.8.0.86:8000/metrics` (vLLM Prometheus) → antrean `running`/`waiting`,
   dijumlahkan lintas engine (server data-parallel, 2 engine).
2. `http://10.8.0.86:8409/api/stats` (monitor host H100accio) → kondisi GPU 0–3,
   yaitu keempat GPU yang menyajikan Gemma di :8000/v1.

Kontrak output (JANGAN diubah tanpa update konsumen):
- Baris TERAKHIR: `vLLM queue: {'running': N, 'waiting': M}` — dikonsumsi
  `parse_waiting()` di scripts/run_rlfv_batch.py dan aturan SOP §1a
  ("lanjut hanya kalau baris terakhir menunjukkan waiting == 0").
- Kalau metrics tak terjangkau: cetak ERROR dan JANGAN cetak baris queue —
  fail-loud; pemanggil melihat waiting=None dan tetap menunggu, bukan lolos palsu.

Pemakaian:  python scripts/gpu_check.py
Env override: GEMMA_METRICS_URL, GPU_STATS_URL, GPU_INDICES (mis. "0,1,2,3").
"""

import json
import os
import re
import sys
import urllib.request

METRICS_URL = os.environ.get("GEMMA_METRICS_URL", "http://10.8.0.86:8000/metrics")
STATS_URL = os.environ.get("GPU_STATS_URL", "http://10.8.0.86:8409/api/stats")
GPU_INDICES = tuple(
    int(i) for i in os.environ.get("GPU_INDICES", "0,1,2,3").split(",")
)
TIMEOUT_S = 10


# --------------------------------------------------------------------------
# fungsi murni (diuji di tests/test_gpu_check.py)
# --------------------------------------------------------------------------

_RUNNING = re.compile(r"^vllm:num_requests_running\{[^}]*\}\s+([0-9.]+)", re.M)
_WAITING = re.compile(r"^vllm:num_requests_waiting\{[^}]*\}\s+([0-9.]+)", re.M)


def parse_vllm_queue(metrics_text: str) -> tuple[int, int]:
    """Jumlahkan num_requests_running/waiting lintas engine.

    `num_requests_waiting_by_reason` sengaja TIDAK ikut (nama metrik beda,
    regex ber-anchor `\\{` tepat setelah nama) — kalau ikut, waiting dobel.
    """
    running = sum(int(float(v)) for v in _RUNNING.findall(metrics_text))
    waiting = sum(int(float(v)) for v in _WAITING.findall(metrics_text))
    return running, waiting


def summarize_gpus(stats: dict, indices: tuple[int, ...]) -> list[str]:
    """Satu baris ringkas per GPU yang diminta (GPU lain di host diabaikan)."""
    lines = []
    for gpu in stats.get("gpus", []):
        if gpu.get("index") not in indices:
            continue
        lines.append(
            "GPU{index}: util={util}% mem={mem_used_mb}/{mem_total_mb}MB "
            "state={state} owner={owner}".format(
                index=gpu.get("index"),
                util=gpu.get("util"),
                mem_used_mb=gpu.get("mem_used_mb"),
                mem_total_mb=gpu.get("mem_total_mb"),
                state=gpu.get("state", "?"),
                owner=gpu.get("owner", "?"),
            )
        )
    return lines


def format_queue_line(running: int, waiting: int) -> str:
    """Format PERSIS seperti skrip lama — regex parse_waiting bergantung padanya."""
    return f"vLLM queue: {{'running': {running}, 'waiting': {waiting}}}"


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main() -> int:
    # Kondisi GPU: informatif saja — kegagalannya tidak menahan vonis queue.
    try:
        stats = json.loads(_fetch(STATS_URL))
        print(f"host={stats.get('host', '?')}")
        for line in summarize_gpus(stats, GPU_INDICES):
            print(line)
    except Exception as e:  # noqa: BLE001 — informatif, lanjut ke metrics
        print(f"WARN: stats unreachable ({e})")

    # Antrean vLLM: penentu vonis. Gagal ambil = fail-loud tanpa baris queue.
    try:
        metrics = _fetch(METRICS_URL)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: metrics unreachable ({e})")
        return 1

    running, waiting = parse_vllm_queue(metrics)
    print(format_queue_line(running, waiting))
    return 0


if __name__ == "__main__":
    sys.exit(main())
