"""Freeze spec resmi SWE-bench per case → cases/gold/<case_id>/swebench_spec.json.

Sumber: dataset HF princeton-nlp/SWE-bench_Lite (cache lokal
~/.cache/huggingface/datasets). Dijalankan SEKALI per case (dev tooling);
checker hanya membaca file beku (spec desain §3).

    python -m eval.fetch_swebench_spec --case django__django-13660 [--case ...]
        [--dataset princeton-nlp/SWE-bench_Lite] [--split test]
        [--gold-root cases/gold]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_KEYS = ("instance_id", "repo", "version", "base_commit",
                 "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS")


def spec_from_row(row: dict, dataset: str) -> dict:
    missing = [k for k in REQUIRED_KEYS if k not in row]
    if missing:
        raise ValueError(f"row missing keys: {missing}")
    spec = dict(row)  # SELURUH row dibekukan — make_test_spec butuh field lain
    for key in ("FAIL_TO_PASS", "PASS_TO_PASS"):
        if isinstance(spec[key], str):
            spec[key] = json.loads(spec[key])
    spec["_dataset"] = dataset
    spec["_fetched_at"] = datetime.now(timezone.utc).isoformat()
    return spec


def write_spec(spec: dict, gold_root: Path) -> Path:
    out_dir = Path(gold_root) / spec["instance_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "swebench_spec.json"
    out.write_bytes((json.dumps(spec, ensure_ascii=False, indent=1) + "\n")
                    .encode("utf-8"))
    return out


def main(argv: list[str] | None = None, rows: list[dict] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", action="append", required=True, dest="cases")
    ap.add_argument("--dataset", default="princeton-nlp/SWE-bench_Lite")
    ap.add_argument("--split", default="test")
    ap.add_argument("--gold-root", default="cases/gold")
    args = ap.parse_args(argv)

    if rows is None:  # jalur nyata: baca dataset (cache HF lokal)
        from eval._swebench_compat import ensure_resource_shim
        ensure_resource_shim()
        from datasets import load_dataset
        rows = list(load_dataset(args.dataset, split=args.split))
    by_id = {r["instance_id"]: r for r in rows}

    rc = 0
    for case in args.cases:
        if case not in by_id:
            print(json.dumps({"error": "case not in dataset", "case": case}))
            rc = 1
            continue
        out = write_spec(spec_from_row(by_id[case], args.dataset),
                         Path(args.gold_root))
        print(json.dumps({"case": case, "spec": str(out)}))
    return rc


if __name__ == "__main__":
    sys.exit(main())
