"""Tests untuk scripts/gpu_check.py — fungsi murni parsing, tanpa jaringan.

Kontrak yang dijaga:
1. Baris TERAKHIR output format `vLLM queue: {'running': N, 'waiting': M}` —
   dikonsumsi `parse_waiting` di scripts/run_rlfv_batch.py (SOP §1a:
   "lanjut hanya kalau baris terakhir menunjukkan waiting == 0").
2. Waiting/running dijumlahkan lintas engine vLLM (data-parallel = 2 engine).
"""

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "gpu_check", Path(__file__).resolve().parent.parent / "scripts" / "gpu_check.py"
)
gpu_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gpu_check)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from run_rlfv_batch import parse_waiting  # noqa: E402


METRICS_SAMPLE = """\
# HELP vllm:num_requests_running Number of requests in model execution batches.
vllm:num_requests_running{engine="0",model_name="google/gemma-4-31B-it"} 2.0
vllm:num_requests_running{engine="1",model_name="google/gemma-4-31B-it"} 1.0
vllm:num_requests_waiting{engine="0",model_name="google/gemma-4-31B-it"} 3.0
vllm:num_requests_waiting{engine="1",model_name="google/gemma-4-31B-it"} 0.0
vllm:num_requests_waiting_by_reason{engine="0",reason="capacity"} 3.0
"""

STATS_SAMPLE = {
    "host": "H100accio",
    "gpus": [
        {"index": 0, "util": 100, "mem_used_mb": 75951, "mem_total_mb": 81559,
         "owner": "derry-gemma4-31b-dp", "state": "busy"},
        {"index": 1, "util": 0, "mem_used_mb": 75949, "mem_total_mb": 81559,
         "owner": "derry-gemma4-31b-dp", "state": "idle"},
        {"index": 2, "util": 0, "mem_used_mb": 76005, "mem_total_mb": 81559,
         "owner": "derry-gemma4-31b-dp", "state": "idle"},
        {"index": 3, "util": 5, "mem_used_mb": 76005, "mem_total_mb": 81559,
         "owner": "derry-gemma4-31b-dp", "state": "idle"},
        {"index": 4, "util": 90, "mem_used_mb": 80000, "mem_total_mb": 81559,
         "owner": "orang-lain", "state": "busy"},
    ],
}


def test_parse_vllm_queue_sums_across_engines():
    running, waiting = gpu_check.parse_vllm_queue(METRICS_SAMPLE)
    assert running == 3
    assert waiting == 3


def test_parse_vllm_queue_ignores_by_reason_lines():
    # num_requests_waiting_by_reason TIDAK boleh dobel-hitung ke waiting
    text = METRICS_SAMPLE.replace('reason="capacity"} 3.0', 'reason="capacity"} 99.0')
    _, waiting = gpu_check.parse_vllm_queue(text)
    assert waiting == 3


def test_parse_vllm_queue_empty_metrics_is_zero():
    running, waiting = gpu_check.parse_vllm_queue("# kosong\n")
    assert (running, waiting) == (0, 0)


def test_summarize_gpus_filters_to_requested_indices():
    lines = gpu_check.summarize_gpus(STATS_SAMPLE, indices=(0, 1, 2, 3))
    assert len(lines) == 4
    assert all("orang-lain" not in ln for ln in lines)
    assert "GPU0" in lines[0] and "util=100%" in lines[0]


def test_final_line_compatible_with_batch_runner_parse_waiting():
    line = gpu_check.format_queue_line(running=1, waiting=0)
    assert line == "vLLM queue: {'running': 1, 'waiting': 0}"
    assert parse_waiting(line) == 0
    assert parse_waiting(gpu_check.format_queue_line(2, 7)) == 7


def test_parse_waiting_none_when_metrics_unreachable():
    # kontrak fail-loud: kalau metrics gagal diambil, JANGAN cetak baris queue
    # palsu ber-waiting=0; batch runner membaca None → tetap menunggu.
    assert parse_waiting("ERROR: metrics unreachable") is None
