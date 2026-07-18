"""Runner gate REPRODUCE: jalankan repro.py di N container docker SEGAR.

Tiap run = `docker run --rm` baru (container sekali pakai) — memenuhi gate
self-contained (bukan container kerja model) dan idempoten (2 run dibanding).
Output JSON ke stdout: {"runs":[{"output": str, "exit": int}, ...]}.

Pemakaian:
    python harness/stages/repro_sandbox_runner.py --image <img> \
        --repro <path\repro.py> [--runs 2] [--timeout 300]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_once(image: str, repro_host_dir: str, timeout: int,
             patch_host_dir: str | None = None,
             patch_name: str | None = None) -> dict:
    """Satu run di container segar; bila patch diberikan, gold patch
    diterapkan dulu (mode flip-test L2)."""
    mounts = ["-v", f"{repro_host_dir}:/pipe-in:ro"]
    apply_step = ""
    if patch_host_dir and patch_name:
        mounts += ["-v", f"{patch_host_dir}:/patch-in:ro"]
        apply_step = f"git apply /patch-in/{patch_name} && "
    cmd = [
        "docker", "run", "--rm", *mounts,
        image,
        "bash", "-lc",
        "mkdir -p /testbed/.pipe && cp /pipe-in/repro.py /testbed/.pipe/repro.py "
        f"&& cd /testbed && {apply_step}python /testbed/.pipe/repro.py 2>&1",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return {"output": p.stdout + (p.stderr or ""), "exit": p.returncode}
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") if isinstance(e.stdout, str) else ""
        return {"output": out + "\n[runner] TIMEOUT", "exit": -1}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--repro", required=True, help="path host ke repro.py")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--patch", default=None,
                    help="path host ke gold.patch — bila di-set, patch "
                         "diterapkan sebelum run (mode flip-test)")
    args = ap.parse_args()

    repro = Path(args.repro).resolve()
    if not repro.is_file():
        print(json.dumps({"error": f"repro tidak ditemukan: {repro}"}))
        return 2

    patch_dir = patch_name = None
    if args.patch:
        patch = Path(args.patch).resolve()
        if not patch.is_file():
            print(json.dumps({"error": f"patch tidak ditemukan: {patch}"}))
            return 2
        patch_dir, patch_name = str(patch.parent), patch.name

    runs = [run_once(args.image, str(repro.parent), args.timeout,
                     patch_host_dir=patch_dir, patch_name=patch_name)
            for _ in range(args.runs)]
    print(json.dumps({"runs": runs}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
