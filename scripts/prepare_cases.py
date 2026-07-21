"""Setup case baru SWE-bench_Lite → cases/problems + cases/gold.

Pola reusable (SOP §1d — menggantikan prepare_10914.py yang hilang). Untuk tiap
case menulis:
  cases/problems/<id>.txt        problem_statement
  cases/gold/<id>/gold.patch     gold source patch
  cases/gold/<id>/gold.json      {"file": <file utama gold>} (untuk file_match)
  cases/gold/<id>/swebench_spec.json  spec resmi beku (reuse fetch_swebench_spec)

Sumber: dataset HF princeton-nlp/SWE-bench_Lite (cache lokal). Dev tooling, sekali
jalan per case. Butuh shim `resource` di Windows (ensure_resource_shim).

    python -m scripts.prepare_cases --case django__django-12497 [--case ...]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

MAIN = Path(__file__).resolve().parent.parent


class GoldPatchCorrupt(RuntimeError):
    """gold.patch gagal parse (`git apply --numstat`) — fail-fast setup."""


def validate_gold_patch_parses(patch_path: Path | str) -> None:
    """Fail-fast R18/KL-G3-1: pastikan gold.patch PARSE bersih.

    Menjalankan `git apply --numstat <patch>` (cek PARSE murni — TIDAK
    `--check`, yang butuh worktree django target yang belum ada di prep-time).
    `--numstat` mem-parse patch & melaporkan jumlah baris per-file TANPA
    menyentuh tree apa pun; keluar non-zero dengan `error: corrupt patch at
    line N` untuk patch malformed (mis. body hunk kurang baris konteks trailing
    vs header @@ — kelas korupsi KH-16). cwd = MAIN (root repo harness, sebuah
    git repo) supaya `git apply` punya konteks git.

    Raise GoldPatchCorrupt (menyebut path + error git) bila korup; return
    None bila bersih.
    """
    patch_path = Path(patch_path)
    proc = subprocess.run(
        ["git", "apply", "--numstat", str(patch_path)],
        cwd=str(MAIN), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise GoldPatchCorrupt(
            f"gold.patch korup / tak-parse: {patch_path} — git apply "
            f"--numstat exit {proc.returncode}: {detail}"
        )


def gold_file_from_patch(patch: str) -> str:
    """File utama yang disentuh gold patch (baris '+++ b/<path>' pertama)."""
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            return line[len("+++ b/"):].strip()
    m = re.search(r"^diff --git a/\S+ b/(\S+)", patch, re.M)
    return m.group(1) if m else ""


def gold_files_all(patch: str) -> list[str]:
    return [ln[len("+++ b/"):].strip() for ln in patch.splitlines()
            if ln.startswith("+++ b/")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", action="append", required=True, dest="cases")
    ap.add_argument("--dataset", default="princeton-nlp/SWE-bench_Lite")
    ap.add_argument("--split", default="test")
    args = ap.parse_args(argv)

    from eval._swebench_compat import ensure_resource_shim
    ensure_resource_shim()
    from datasets import load_dataset
    from eval.fetch_swebench_spec import spec_from_row, write_spec

    rows = {r["instance_id"]: r
            for r in load_dataset(args.dataset, split=args.split)}

    problems = MAIN / "cases" / "problems"
    gold_root = MAIN / "cases" / "gold"
    problems.mkdir(parents=True, exist_ok=True)

    rc = 0
    for case in args.cases:
        if case not in rows:
            print(json.dumps({"error": "case not in dataset", "case": case}))
            rc = 1
            continue
        row = rows[case]
        (problems / f"{case}.txt").write_bytes(
            (row["problem_statement"].rstrip() + "\n").encode("utf-8"))
        gdir = gold_root / case
        gdir.mkdir(parents=True, exist_ok=True)
        patch = row["patch"]
        # JANGAN rstrip patch: patch SWE-bench sering berakhir dengan baris
        # konteks whitespace-only (spasi tunggal = baris kosong di source) yang
        # WAJIB dipertahankan. rstrip() menghapusnya -> body hunk kurang 1 baris
        # dari header @@ -a,b +c,d @@ -> `git apply` gagal "corrupt patch"
        # -> flip test short-circuit -> verdict wrong-logic MISLABEL (KH-16).
        # Cukup pastikan tepat satu newline penutup.
        if not patch.endswith("\n"):
            patch += "\n"
        gold_patch_path = gdir / "gold.patch"
        gold_patch_path.write_bytes(patch.encode("utf-8"))
        # R18/KL-G3-1: fail-fast — tolak gold.patch yang tak parse (KH-16).
        # Ketimbang diam-diam lolos & lahir verdict wrong-logic vacuous nanti.
        validate_gold_patch_parses(gold_patch_path)
        files = gold_files_all(patch)
        (gdir / "gold.json").write_bytes(
            (json.dumps({"file": gold_file_from_patch(patch)},
                        ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
        write_spec(spec_from_row(row, args.dataset), gold_root)
        print(json.dumps({"case": case, "gold_file": gold_file_from_patch(patch),
                          "gold_files_all": files}))
    return rc


if __name__ == "__main__":
    sys.exit(main())
