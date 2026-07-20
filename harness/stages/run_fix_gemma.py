"""Driver stage FIX untuk Gemma (f-dev v0).

Spec: docs/superpowers/specs/2026-07-20-fix-stage-design.md.
Arsitektur: HARNESS mengiterasi kandidat dari candidates.md run L qualified
(urutan tulis, tanpa prioritas); satu attempt = satu kandidat = sesi Gemma
FRESH + container kerja BARU (pristine by construction). Bukti-dulu: DONE
ditolak sampai driver menyaksikan repro.py mencetak PASS (exact_status) di
container kerja; DONE diterima hanya bila pre-check dunia segar lolos
(evaluate_patch_in_fresh_world — fungsi yang SAMA dengan gate). Driver
TIDAK memvonis: exit + verdict.json ditulis run_fix_gates.

Pemakaian (dari root main):
    python harness/stages/run_fix_gemma.py --case django__django-11422
        --rerun 1 --image ghcr.io/...
        --input-localize-files <dir files run L qualified>
        --input-repro-files <dir files run R qualified>
        --problem-file cases/problems/django__django-11422.txt
"""
from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from harness.emit import Emitter
from harness.stages.fix_gates import compose_fix_md, fix_rejection_message
from harness.stages.fix_patch_runner import evaluate_patch_in_fresh_world
from harness.stages.gemma_protocol import (done_rejection_fix, exact_status,
                                           has_done, is_repro_run,
                                           parse_actions, retry_reason,
                                           token_format_note)
from harness.stages.localize_gates import parse_candidates_md

PROTOCOL_NOTE = """
## How to work (action protocol — MANDATORY)

You work through action blocks in your replies. One reply may contain several
blocks; they are executed in order and I send the results back to you.

1. Run a shell command in the /testbed sandbox (read code, edit files, run
   the repro):
```bash
<command>
```
2. Write/overwrite a file with the block's content:
```file:/testbed/path/to/file.py
<full file content>
```
3. Submit the final fix.md artifact (the lines listed in the contract):
```fix.md
<fix.md content>
```
Close with a single line containing exactly:
DONE
Declare DONE only after you have run the repro, seen REPRO_STATUS: PASS in
its output, and submitted the fix.md block.

Work step by step: act, wait for my output, then take the next step based on
what you observed. Keep prose minimal; focus on the next action.
"""


@dataclass(frozen=True)
class FixInputs:
    candidates: list[dict]
    repro_md: str
    repro_py: str


def load_fix_inputs(localize_dir: Path, repro_dir: Path) -> FixInputs:
    """Input beku (spec §9): candidates.md dari run L qualified terakhir,
    repro.md + repro.py dari run R qualified terakhir."""
    candidates = parse_candidates_md(
        (localize_dir / "candidates.md").read_text(encoding="utf-8"))
    return FixInputs(
        candidates=candidates,
        repro_md=(repro_dir / "repro.md").read_text(encoding="utf-8"),
        repro_py=(repro_dir / "repro.py").read_text(encoding="utf-8"))


def compose_fix_seed(problem: str, repro_md: str, repro_py: str,
                     candidate: dict) -> str:
    """Seed per attempt (spec §3, English): problem + repro.md verbatim +
    ISI repro.py (P21: model melihat lembar ujiannya) + kandidat AKTIF
    saja (scope positif; kandidat lain tidak pernah disebut)."""
    return ("PROBLEM STATEMENT:\n" + problem
            + "\n\nREPRODUCE ARTIFACTS (frozen input, already "
              "gate-approved):\n" + repro_md
            + "\nThe frozen repro script is installed at "
              "/testbed/.pipe/repro.py; this is its content:\n"
            + "```python\n" + repro_py + "\n```\n"
            + "\nYOUR EDIT SITE:\n"
            + f"file: {candidate['file']}\n"
            + f"evidence: {candidate['evidence']}\n"
            + f"expectation: {candidate['expectation']}\n"
            + "\nStart working now. The /testbed sandbox is at the base "
              "commit; the bug is present.")


def chat(endpoint: str, model: str, messages: list[dict],
         timeout: int = 600) -> str:
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 2048,
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    return data["choices"][0]["message"]["content"] or ""


def docker_exec(container: str, cmd: str, timeout: int = 180) -> tuple[str, int]:
    p = subprocess.run(
        ["docker", "exec", container, "bash", "-lc", cmd],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    return (p.stdout or "") + (p.stderr or ""), p.returncode


def docker_write_file(container: str, path: str, body: str) -> None:
    # Bytes mentah, BUKAN text=True (pelajaran r15: mode teks Windows
    # menulis \r\n ke pipe; kontrak §2: byte \r adalah BUG).
    data = body.replace("\r\n", "\n").encode("utf-8")
    subprocess.run(
        ["docker", "exec", "-i", container, "bash", "-lc",
         f"mkdir -p $(dirname '{path}') && cat > '{path}'"],
        input=data, check=True, timeout=60,
    )


def tail(s: str, n: int = 4000) -> str:
    return s if len(s) <= n else "[...dipotong...]\n" + s[-n:]


def _ensure_nl(s: str) -> str:
    return s if not s or s.endswith("\n") else s + "\n"


DIFF_CMD = ("cd /testbed && git add -N -- . ':(exclude).pipe' "
            ">/dev/null 2>&1; git diff 2>/dev/null")


def collect_work_diff(container: str) -> str:
    """Diff container kerja: `git add -N` (file baru ter-cover, kontrak
    §10) dengan .pipe dikecualikan (workspace probe bukan bagian fix),
    lalu `git diff`. Gagal baca -> "" (diff kosong ditolak evaluator)."""
    out, code = docker_exec(container, DIFF_CMD, timeout=120)
    return out if code == 0 else ""


def emit_abort(em: Emitter, reason: str) -> None:
    """Tutup run crash sesuai kontrak §8."""
    em.event("fix", "abort", detail={"reason": reason})
    em.write_verdict(phases={}, wall="abort", pass_l1=None, pass_l2=None)
    em.run_end({"fix": "abort"}, "abort")
