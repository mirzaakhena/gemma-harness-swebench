# SWE-bench Checker (L2) + Dashboard 2-Lapisan — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modul eval realm-dev `eval/swebench_checker.py` yang memvonis `resolved` via grading resmi SWE-bench (F2P+P2P), plus dashboard status 2-lapisan (PASS = `pass_l1` ∧ `resolved`) di tab "FIX and VERIFY".

**Architecture:** Checker = pure functions (komposisi skrip eval + grading host-side via paket `swebench` v4.1.0) + lapisan docker terpisah (container Epoch segar sekali pakai). Hasil ke file terpisah `swebench_eval.json` di run dir (pola `gold_eval.json`); `verdict.json`/`events.jsonl` TIDAK PERNAH disentuh. Dashboard merge saat render (viewer read-only). Spec: `docs/superpowers/specs/2026-07-20-swebench-checker-l2-design.md`.

**Tech Stack:** Python stdlib + pytest; paket terpasang `swebench` 4.1.0 (grading + konstanta + log parser resmi) dan `datasets` 4.8.5 (fetch spec beku dari cache HF); docker image Epoch `ghcr.io/epoch-research/swe-bench.eval.x86_64.<case_id>:latest`.

## Global Constraints

- Repo kerja: `C:\Users\Mirza\workspace\gemma-harness-swebench\main`, branch `main` (konvensi proyek — tanpa worktree).
- `python -m pytest -q` dari root `main\` HIJAU sebelum TIAP commit (baseline saat plan ditulis: 345 passed).
- Nol docker & nol network di test suite (mock/monkeypatch; pola test FIX: 46 test 0.24s).
- SEMUA import `swebench`/`inspect_evals` WAJIB didahului shim `resource` (`eval/_swebench_compat.ensure_resource_shim()`) — import langsung crash di Windows.
- File baru UTF-8 tanpa BOM, newline LF; file yang dikirim ke docker ditulis `newline="\n"` (jebakan CRLF).
- Tulis/edit file pakai tool Write/Edit, BUKAN heredoc bash / PowerShell `Set-Content` (mojibake).
- Checker realm dev: tidak menyentuh `verdict.json`/`events.jsonl`, hasil tidak pernah diumpankan ke loop Gemma.
- Commit message ditulis ke file scratchpad lalu `git commit -F <file>` (PowerShell 5.1 memecah kutip ganda pada `-m`). Trailer WAJIB tiap commit:

```
Agent: bot-05

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

- Fakta API terverifikasi 2026-07-20 (jangan re-riset): `get_eval_report(test_spec, prediction, test_log_path, include_tests_status)` → `{instance_id: {resolved, patch_successfully_applied, tests_status{FAIL_TO_PASS{success,failure}, PASS_TO_PASS{...}}}}`; `make_test_spec(instance_dict)` butuh key `instance_id, repo, version, base_commit, test_patch` (+`FAIL_TO_PASS`/`PASS_TO_PASS` boleh list atau JSON-string); `KEY_PREDICTION == "model_patch"`; marker log `">>>>> Start Test Output"`/`">>>>> End Test Output"` (pakai konstanta, jangan hardcode); test_cmd django dari `MAP_REPO_VERSION_TO_SPECS["django/django"][version]["test_cmd"]`; parser django mengenali baris `test_x (mod.Class) ... ok|FAIL|ERROR`; direktori test dari `swebench.harness.test_spec.python.get_test_directives({"repo", "test_patch"})`.

---

### Task 1: Shim kompat Windows — `eval/_swebench_compat.py`

**Files:**
- Create: `eval/_swebench_compat.py`
- Test: `tests/test_swebench_compat.py`

**Interfaces:**
- Produces: `ensure_resource_shim() -> None` — idempoten; setelah dipanggil, `import swebench.*` aman di Windows. Dipakai Task 2, 4, 5, (probe Task 3).

- [ ] **Step 1: Write the failing test**

```python
"""Test shim resource utk paket swebench di Windows."""
import sys


def test_shim_allows_swebench_import():
    from eval._swebench_compat import ensure_resource_shim
    ensure_resource_shim()
    from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS
    assert "django/django" in MAP_REPO_VERSION_TO_SPECS


def test_shim_idempotent():
    from eval._swebench_compat import ensure_resource_shim
    ensure_resource_shim()
    before = sys.modules["resource"]
    ensure_resource_shim()
    assert sys.modules["resource"] is before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_swebench_compat.py -v` (dari root `main\`)
Expected: FAIL/ERROR `ModuleNotFoundError: No module named 'eval._swebench_compat'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Kompat Windows utk paket swebench: modul `resource` (Unix-only) di-shim
sebelum import swebench apa pun. SEMUA import swebench di repo ini lewat
ensure_resource_shim() dulu — import langsung crash di Windows."""
from __future__ import annotations

import sys
import types


def ensure_resource_shim() -> None:
    if "resource" in sys.modules:
        return
    m = types.ModuleType("resource")
    m.getrlimit = lambda *a: (0, 0)
    m.setrlimit = lambda *a: None
    m.RLIMIT_NOFILE = 7
    sys.modules["resource"] = m
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_swebench_compat.py -v` lalu `python -m pytest -q`
Expected: 2 passed; suite penuh hijau (345 + 2).

- [ ] **Step 5: Commit**

Pesan: `feat(eval): shim resource Windows utk paket swebench` (+ trailer wajib).

---

### Task 2: Fetch & freeze spec — `eval/fetch_swebench_spec.py`

**Files:**
- Create: `eval/fetch_swebench_spec.py`
- Test: `tests/test_fetch_swebench_spec.py`

**Interfaces:**
- Consumes: `ensure_resource_shim` (Task 1) — dipanggil di `main()` sebelum `import datasets` (datasets → dill aman, tapi konsisten saja; wajib bila kelak menyentuh swebench).
- Produces: `spec_from_row(row: dict, dataset: str) -> dict` (freeze SELURUH row + decode F2P/P2P + provenance `_dataset`/`_fetched_at`); `write_spec(spec: dict, gold_root: Path) -> Path` (tulis `<gold_root>/<instance_id>/swebench_spec.json`); CLI `python -m eval.fetch_swebench_spec --case <id> [--case <id2> ...]`.

- [ ] **Step 1: Write the failing test**

```python
"""Test freeze spec SWE-bench per case (tanpa network)."""
import json

from eval.fetch_swebench_spec import spec_from_row, write_spec

ROW = {"instance_id": "django__django-99999", "repo": "django/django",
       "version": "3.0", "base_commit": "abc123",
       "environment_setup_commit": "def456",
       "problem_statement": "bug report text", "patch": "--- a/x.py\n",
       "test_patch": "--- a/tests/foo/tests.py\n+++ b/tests/foo/tests.py\n",
       "FAIL_TO_PASS": "[\"test_a (foo.tests.FooTest)\"]",
       "PASS_TO_PASS": "[\"test_b (foo.tests.FooTest)\"]"}


def test_spec_from_row_decodes_lists_and_adds_provenance():
    spec = spec_from_row(dict(ROW), dataset="princeton-nlp/SWE-bench_Lite")
    assert spec["FAIL_TO_PASS"] == ["test_a (foo.tests.FooTest)"]
    assert spec["PASS_TO_PASS"] == ["test_b (foo.tests.FooTest)"]
    assert spec["_dataset"] == "princeton-nlp/SWE-bench_Lite"
    assert spec["_fetched_at"]
    assert spec["base_commit"] == "abc123"  # row lain ikut beku utuh


def test_spec_from_row_missing_key_raises():
    row = dict(ROW)
    del row["test_patch"]
    try:
        spec_from_row(row, dataset="d")
        raise AssertionError("should raise")
    except ValueError as e:
        assert "test_patch" in str(e)


def test_write_spec_utf8_lf_no_bom(tmp_path):
    spec = spec_from_row(dict(ROW), dataset="d")
    out = write_spec(spec, tmp_path)
    assert out == tmp_path / "django__django-99999" / "swebench_spec.json"
    raw = out.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert json.loads(raw.decode("utf-8"))["instance_id"] == ROW["instance_id"]


def test_main_with_injected_rows(tmp_path, capsys):
    from eval.fetch_swebench_spec import main
    rc = main(["--case", "django__django-99999", "--gold-root",
               str(tmp_path)], rows=[dict(ROW)])
    assert rc == 0
    assert (tmp_path / "django__django-99999" / "swebench_spec.json").is_file()


def test_main_unknown_case_errors(tmp_path):
    from eval.fetch_swebench_spec import main
    rc = main(["--case", "nope", "--gold-root", str(tmp_path)],
              rows=[dict(ROW)])
    assert rc == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fetch_swebench_spec.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'eval.fetch_swebench_spec'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_fetch_swebench_spec.py -v` lalu `python -m pytest -q`
Expected: 5 passed; suite penuh hijau.

- [ ] **Step 5: Commit**

Pesan: `feat(eval): fetch & freeze swebench_spec.json per case dari dataset HF` (+ trailer).

---

### Task 3: PROBE end-to-end di 13660 (validasi asumsi — SEBELUM modul final)

Spec §8.1: asumsi yang belum teruji end-to-end divalidasi dulu dengan skrip kasar sekali pakai. TIDAK ada commit kode di task ini (hanya temuan). Jika ada asumsi patah (conda path, argumen runtests, format log, grading), CATAT dan sesuaikan Task 4-6 sebelum lanjut.

**Files:**
- Scratchpad (di luar repo): `probe_13660.py`
- Uses: `eval/fetch_swebench_spec.py` (Task 2)

- [ ] **Step 1: Freeze spec 13660 (jalur nyata, cache HF)**

Run (dari root `main\`): `python -m eval.fetch_swebench_spec --case django__django-13660`
Expected: `{"case": "django__django-13660", "spec": "cases\\gold\\django__django-13660\\swebench_spec.json"}`; file berisi `test_patch` non-kosong dan list `FAIL_TO_PASS`/`PASS_TO_PASS`. JANGAN commit dulu (ikut Task 9).

- [ ] **Step 2: Tulis skrip probe ke scratchpad** (pakai tool Write)

```python
"""Probe kasar checker L2 — validasi asumsi sebelum TDD (sekali pakai)."""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent

MAIN = Path(r"C:\Users\Mirza\workspace\gemma-harness-swebench\main")
sys.path.insert(0, str(MAIN))
from eval._swebench_compat import ensure_resource_shim  # noqa: E402
ensure_resource_shim()
from swebench.harness.constants import (  # noqa: E402
    END_TEST_OUTPUT, KEY_INSTANCE_ID, KEY_PREDICTION,
    MAP_REPO_VERSION_TO_SPECS, START_TEST_OUTPUT)
from swebench.harness.grading import get_eval_report  # noqa: E402
from swebench.harness.test_spec.python import get_test_directives  # noqa: E402
from swebench.harness.test_spec.test_spec import make_test_spec  # noqa: E402

CASE = "django__django-13660"
IMAGE = f"ghcr.io/epoch-research/swe-bench.eval.x86_64.{CASE}:latest"
spec = json.loads((MAIN / "cases" / "gold" / CASE /
                   "swebench_spec.json").read_text(encoding="utf-8"))
fix_diff = Path(sys.argv[1]).read_text(encoding="utf-8")  # patch yang diuji

specs = MAP_REPO_VERSION_TO_SPECS[spec["repo"]][spec["version"]]
test_cmd = specs["test_cmd"]
if isinstance(test_cmd, list):
    test_cmd = test_cmd[-1]
tp_files = re.findall(r"--- a/(.*)", spec["test_patch"])
directives = get_test_directives({"repo": spec["repo"],
                                  "test_patch": spec["test_patch"]})
nl = "\n"
script = dedent(f"""\
    #!/bin/bash
    set -uo pipefail -x
    cd /testbed
    set +x
    source /opt/miniconda3/bin/activate
    conda activate testbed
    set -x
    {nl.join(specs.get("eval_commands", []))}
    cd /testbed
    {specs.get("install", "")}
    git apply --check /patch-in/fix.diff || {{ echo FIX_APPLY_FAILED; exit 2; }}
    git apply /patch-in/fix.diff
    git checkout {spec["base_commit"]} {" ".join(tp_files)}
    git apply /patch-in/test_patch.diff
    set +x
    echo '{START_TEST_OUTPUT}'
    {test_cmd} {" ".join(directives)}
    echo '{END_TEST_OUTPUT}'
""")
tmp = Path(tempfile.mkdtemp(prefix="probe-l2-"))
for name, body in (("eval.sh", script), ("fix.diff", fix_diff),
                   ("test_patch.diff", spec["test_patch"])):
    (tmp / name).write_text(
        body if body.endswith("\n") else body + "\n",
        encoding="utf-8", newline="\n")
p = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp}:/patch-in:ro",
                    IMAGE, "bash", "/patch-in/eval.sh"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=3600)
log = tmp / "test_output.log"
log.write_text((p.stdout or "") + (p.stderr or ""), encoding="utf-8",
               newline="\n")
print("exit:", p.returncode, "| log:", log)
report = get_eval_report(
    make_test_spec(spec),
    {KEY_INSTANCE_ID: CASE, KEY_PREDICTION: fix_diff,
     "model_name_or_path": "probe"},
    str(log), include_tests_status=True)[CASE]
print(json.dumps({k: report[k] for k in
                  ("patch_successfully_applied", "resolved")}, indent=1))
ts = report.get("tests_status") or {}
for grp in ("FAIL_TO_PASS", "PASS_TO_PASS"):
    g = ts.get(grp) or {}
    print(grp, "success:", len(g.get("success", [])),
          "failure:", g.get("failure", []))
```

- [ ] **Step 3: Probe dengan GOLD patch (sanity — wajib resolved=true)**

Run: `python <scratchpad>\probe_13660.py C:\Users\Mirza\workspace\gemma-harness-swebench\main\cases\gold\django__django-13660\gold.patch`
Expected: `patch_successfully_applied: true`, `resolved: true`, F2P failure `[]`, P2P failure `[]`. Bila TIDAK → asumsi patah; autopsi log di tmp dir, catat temuan, sesuaikan template skrip Task 4 sebelum lanjut.

- [ ] **Step 4: Probe dengan fix.diff Gemma run r1**

Run: `python <scratchpad>\probe_13660.py C:\Users\Mirza\workspace\gemma-harness-swebench\artifacts\f-dev\f-dev--django__django-13660--r1\files\fix.diff`
Expected (dugaan, BUKAN kepastian): `resolved: true`. Apa pun hasilnya = data valid; catat.

- [ ] **Step 5: Laporkan temuan probe ke Mirza (Telegram) + catat di vault F-dev Log** (blok "Probe checker L2"), termasuk durasi run test (bahan set default `--timeout`).

---

### Task 4: Core pure checker — `eval/swebench_checker.py` (tanpa CLI)

**Files:**
- Create: `eval/swebench_checker.py`
- Test: `tests/test_swebench_checker.py`

**Interfaces:**
- Consumes: `ensure_resource_shim` (Task 1).
- Produces: `load_spec(spec_path: Path) -> dict` (raise FileNotFoundError/ValueError dgn pesan menyuruh fetch); `build_eval_script(spec: dict) -> str` (bash utk container: apply `/patch-in/fix.diff` → reset & apply `/patch-in/test_patch.diff` → jalankan test ber-marker); `grade_log(spec: dict, fix_diff_text: str, log_path: Path) -> dict` (report mentah satu instance dari `get_eval_report`); `summarize_report(raw: dict, spec: dict, case: str, rerun: int, image: str, spec_path: str, log_rel: str, checked_at: str) -> dict` (skema `swebench_eval.json` spec §5).

- [ ] **Step 1: Write the failing test**

```python
"""Test core pure checker SWE-bench L2 — tanpa docker, tanpa network."""
import pytest

from eval._swebench_compat import ensure_resource_shim

ensure_resource_shim()
from swebench.harness.constants import END_TEST_OUTPUT, START_TEST_OUTPUT

from eval.swebench_checker import (build_eval_script, grade_log, load_spec,
                                   summarize_report)

SPEC = {"instance_id": "django__django-99999", "repo": "django/django",
        "version": "3.0", "base_commit": "abc123",
        "environment_setup_commit": "abc123",
        "test_patch": ("diff --git a/tests/foo/tests.py b/tests/foo/tests.py\n"
                       "--- a/tests/foo/tests.py\n+++ b/tests/foo/tests.py\n"
                       "@@ -1 +1,2 @@\n pass\n+pass\n"),
        "FAIL_TO_PASS": ["test_a (foo.tests.FooTest)"],
        "PASS_TO_PASS": ["test_b (foo.tests.FooTest)"]}

DIFF = "--- a/django/x.py\n+++ b/django/x.py\n@@ -1 +1 @@\n-a\n+b\n"


def _log(body: str) -> str:
    return f"{START_TEST_OUTPUT}\n{body}\n{END_TEST_OUTPUT}\n"


def test_load_spec_missing_file_mentions_fetch(tmp_path):
    with pytest.raises(FileNotFoundError) as e:
        load_spec(tmp_path / "swebench_spec.json")
    assert "fetch_swebench_spec" in str(e.value)


def test_build_eval_script_shape():
    script = build_eval_script(SPEC)
    assert "conda activate testbed" in script
    assert "git apply /patch-in/fix.diff" in script
    assert "git apply /patch-in/test_patch.diff" in script
    assert f"git checkout {SPEC['base_commit']} tests/foo/tests.py" in script
    assert START_TEST_OUTPUT in script and END_TEST_OUTPUT in script
    assert "runtests.py" in script          # test_cmd django dari peta resmi
    assert "foo" in script.split(START_TEST_OUTPUT)[1]  # direktif test


def test_grade_log_resolved_true(tmp_path):
    log = tmp_path / "out.log"
    log.write_text(_log("test_a (foo.tests.FooTest) ... ok\n"
                        "test_b (foo.tests.FooTest) ... ok"),
                   encoding="utf-8")
    raw = grade_log(SPEC, DIFF, log)
    assert raw["patch_successfully_applied"] is True
    assert raw["resolved"] is True


def test_grade_log_p2p_regression(tmp_path):
    log = tmp_path / "out.log"
    log.write_text(_log("test_a (foo.tests.FooTest) ... ok\n"
                        "test_b (foo.tests.FooTest) ... FAIL"),
                   encoding="utf-8")
    raw = grade_log(SPEC, DIFF, log)
    assert raw["resolved"] is False
    assert raw["tests_status"]["PASS_TO_PASS"]["failure"] == [
        "test_b (foo.tests.FooTest)"]


def test_grade_log_no_markers_means_apply_failed(tmp_path):
    log = tmp_path / "out.log"
    log.write_text("FIX_APPLY_FAILED\n", encoding="utf-8")
    raw = grade_log(SPEC, DIFF, log)
    assert raw["patch_successfully_applied"] is False
    assert raw["resolved"] is False


def test_summarize_report_schema(tmp_path):
    log = tmp_path / "out.log"
    log.write_text(_log("test_a (foo.tests.FooTest) ... ok\n"
                        "test_b (foo.tests.FooTest) ... FAIL"),
                   encoding="utf-8")
    raw = grade_log(SPEC, DIFF, log)
    s = summarize_report(raw, SPEC, case="django__django-99999", rerun=1,
                         image="img:latest", spec_path="cases/gold/x.json",
                         log_rel="files/swebench_test_output.log",
                         checked_at="2026-07-20T00:00:00+00:00")
    assert s["case"] == "django__django-99999" and s["rerun"] == 1
    assert s["resolved"] is False
    assert s["f2p_passed"] == ["test_a (foo.tests.FooTest)"]
    assert s["f2p_failed"] == []
    assert s["p2p_failed"] == ["test_b (foo.tests.FooTest)"]
    assert s["p2p_passed_count"] == 0
    assert s["image"] == "img:latest" and s["checked_at"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_swebench_checker.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'eval.swebench_checker'`

- [ ] **Step 3: Write minimal implementation**

```python
"""SWE-bench checker (L2) — eval realm-dev, penghasil vonis `resolved`.

Spec: docs/superpowers/specs/2026-07-20-swebench-checker-l2-design.md.
Vonis via grading RESMI paket swebench (get_eval_report); eksekusi test di
container Epoch segar (lapisan docker: eval/swebench_runner.py, Task 5;
CLI: Task 6). Hasil ke swebench_eval.json — TIDAK menyentuh verdict.json /
events.jsonl; tidak pernah diumpankan ke loop model (boundary integritas).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from textwrap import dedent

from eval._swebench_compat import ensure_resource_shim

REQUIRED_KEYS = ("instance_id", "repo", "version", "base_commit",
                 "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS")


def load_spec(spec_path: Path) -> dict:
    p = Path(spec_path)
    if not p.is_file():
        raise FileNotFoundError(
            f"swebench_spec.json not found: {p} — run "
            f"`python -m eval.fetch_swebench_spec --case <case_id>` first")
    spec = json.loads(p.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_KEYS if k not in spec]
    if missing:
        raise ValueError(f"swebench_spec.json missing keys: {missing}")
    return spec


def build_eval_script(spec: dict) -> str:
    """Bash utk container Epoch segar: fix.diff model → test_patch resmi →
    test F2P∪P2P ber-marker (pola inspect_evals, terbukti utk image Epoch).
    Gagal apply fix → exit 2 tanpa marker (grading: applied=False)."""
    ensure_resource_shim()
    from swebench.harness.constants import (END_TEST_OUTPUT,
                                            MAP_REPO_VERSION_TO_SPECS,
                                            START_TEST_OUTPUT)
    from swebench.harness.test_spec.python import get_test_directives
    specs = MAP_REPO_VERSION_TO_SPECS[spec["repo"]][spec["version"]]
    test_cmd = specs["test_cmd"]
    if isinstance(test_cmd, list):
        test_cmd = test_cmd[-1]
    tp_files = re.findall(r"--- a/(.*)", spec["test_patch"])
    directives = get_test_directives({"repo": spec["repo"],
                                      "test_patch": spec["test_patch"]})
    nl = "\n"
    return dedent(f"""\
        #!/bin/bash
        set -uo pipefail -x
        cd /testbed
        set +x
        source /opt/miniconda3/bin/activate
        conda activate testbed
        set -x
        {nl.join(specs.get("eval_commands", []))}
        cd /testbed
        {specs.get("install", "")}
        git apply --check /patch-in/fix.diff || {{ echo FIX_APPLY_FAILED; exit 2; }}
        git apply /patch-in/fix.diff
        git checkout {spec["base_commit"]} {" ".join(tp_files)}
        git apply /patch-in/test_patch.diff
        set +x
        echo '{START_TEST_OUTPUT}'
        {test_cmd} {" ".join(directives)}
        echo '{END_TEST_OUTPUT}'
    """)


def grade_log(spec: dict, fix_diff_text: str, log_path: Path) -> dict:
    """Vonis resmi host-side: log parser per-repo + get_eval_report."""
    ensure_resource_shim()
    from swebench.harness.constants import KEY_INSTANCE_ID, KEY_PREDICTION
    from swebench.harness.grading import get_eval_report
    from swebench.harness.test_spec.test_spec import make_test_spec
    prediction = {KEY_INSTANCE_ID: spec["instance_id"],
                  KEY_PREDICTION: fix_diff_text,
                  "model_name_or_path": "gemma-harness"}
    return get_eval_report(make_test_spec(dict(spec)), prediction,
                           str(log_path),
                           include_tests_status=True)[spec["instance_id"]]


def summarize_report(raw: dict, spec: dict, case: str, rerun: int,
                     image: str, spec_path: str, log_rel: str,
                     checked_at: str) -> dict:
    """Skema swebench_eval.json (spec §5) — KAYA: regresi per nama test."""
    tests = raw.get("tests_status") or {}
    f2p = tests.get("FAIL_TO_PASS") or {"success": [], "failure": []}
    p2p = tests.get("PASS_TO_PASS") or {"success": [], "failure": []}
    return {"case": case, "rerun": rerun,
            "resolved": bool(raw.get("resolved")),
            "patch_successfully_applied":
                bool(raw.get("patch_successfully_applied")),
            "f2p_passed": list(f2p.get("success", [])),
            "f2p_failed": list(f2p.get("failure", [])),
            "p2p_passed_count": len(p2p.get("success", [])),
            "p2p_failed": list(p2p.get("failure", [])),
            "image": image, "spec": spec_path, "log": log_rel,
            "checked_at": checked_at}
```

CATATAN: bila temuan probe (Task 3) menuntut penyesuaian skrip (mis. env command tambahan), terapkan DI SINI dan sesuaikan assert test — jangan biarkan template menyimpang dari yang terbukti jalan.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_swebench_checker.py -v` lalu `python -m pytest -q`
Expected: 6 passed; suite penuh hijau.

- [ ] **Step 5: Commit**

Pesan: `feat(eval): core pure swebench_checker — eval script + grading resmi + skema kaya` (+ trailer).

---

### Task 5: Lapisan docker — `eval/swebench_runner.py`

**Files:**
- Create: `eval/swebench_runner.py`
- Test: `tests/test_swebench_runner.py`

**Interfaces:**
- Produces: `default_image(case_id: str) -> str`; `run_eval_in_container(image: str, eval_script: str, fix_diff: str, test_patch: str, timeout: int = 3600) -> dict` → `{"log": str, "exit": int}`. Dipakai CLI Task 6 (injectable utk test).

- [ ] **Step 1: Write the failing test**

```python
"""Test lapisan docker checker — subprocess di-mock, nol docker nyata."""
from pathlib import Path

import eval.swebench_runner as runner


def test_default_image():
    assert runner.default_image("django__django-13660") == (
        "ghcr.io/epoch-research/swe-bench.eval.x86_64."
        "django__django-13660:latest")


def test_run_eval_in_container_wiring(monkeypatch):
    calls = {}

    class FakeProc:
        returncode = 0
        stdout = "hello-log\n"
        stderr = "warn\n"

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        calls["kw"] = kw
        return FakeProc()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    out = runner.run_eval_in_container("img:x", "#!/bin/bash\necho hi",
                                       "--- a/f\n", "--- a/t\n", timeout=99)
    assert out == {"log": "hello-log\nwarn\n", "exit": 0}
    cmd = calls["cmd"]
    assert cmd[:4] == ["docker", "run", "--rm", "-v"]
    mount = cmd[4]
    assert mount.endswith(":/patch-in:ro")
    tmpdir = Path(mount.split(":/patch-in")[0])
    assert (tmpdir / "eval.sh").is_file()
    for name in ("eval.sh", "fix.diff", "test_patch.diff"):
        raw = (tmpdir / name).read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf") and b"\r\n" not in raw
        assert raw.endswith(b"\n")
    assert cmd[5] == "img:x" and cmd[6:] == ["bash", "/patch-in/eval.sh"]
    assert calls["kw"]["timeout"] == 99
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_swebench_runner.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'eval.swebench_runner'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Lapisan docker checker SWE-bench — container Epoch segar sekali pakai.

Pola mount /patch-in read-only mengikuti fix_patch_runner/repro_sandbox_runner.
stdout+stderr digabung: marker test di stdout, output test runner django
sering di stderr — get_logs_eval punya fallback parse seluruh isi log.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

DEFAULT_IMAGE_TPL = ("ghcr.io/epoch-research/swe-bench.eval.x86_64."
                     "{case_id}:latest")


def default_image(case_id: str) -> str:
    return DEFAULT_IMAGE_TPL.format(case_id=case_id)


def run_eval_in_container(image: str, eval_script: str, fix_diff: str,
                          test_patch: str, timeout: int = 3600) -> dict:
    tmpdir = Path(tempfile.mkdtemp(prefix="swebench-l2-"))
    for name, body in (("eval.sh", eval_script), ("fix.diff", fix_diff),
                       ("test_patch.diff", test_patch)):
        (tmpdir / name).write_text(
            body if body.endswith("\n") else body + "\n",
            encoding="utf-8", newline="\n")
    p = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{tmpdir}:/patch-in:ro", image,
         "bash", "/patch-in/eval.sh"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout)
    return {"log": (p.stdout or "") + (p.stderr or ""), "exit": p.returncode}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_swebench_runner.py -v` lalu `python -m pytest -q`
Expected: 2 passed; suite penuh hijau.

- [ ] **Step 5: Commit**

Pesan: `feat(eval): lapisan docker swebench_runner — container Epoch segar` (+ trailer).

---

### Task 6: CLI checker — `run_checker()` + `main()` di `eval/swebench_checker.py`

**Files:**
- Modify: `eval/swebench_checker.py` (tambah `run_checker` + `main` di bawah fungsi pure)
- Test: `tests/test_swebench_checker.py` (tambah test CLI)

**Interfaces:**
- Consumes: Task 4 (pure) + Task 5 (`default_image`, `run_eval_in_container`).
- Produces: `run_checker(case, rerun, campaign, artifacts, image, spec_path, timeout, runner=None) -> tuple[int, dict]`; CLI `python -m eval.swebench_checker --case <id> --rerun <N> [--campaign f-dev] [--artifacts ../artifacts] [--image ...] [--spec ...] [--timeout 3600]`. Menulis `files/swebench_test_output.log` + `swebench_eval.json` di run dir, echo JSON ke stdout (pola `fix_gold_eval`). Rerun checker menimpa DUA file miliknya sendiri saja.

- [ ] **Step 1: Write the failing tests** (tambahkan ke `tests/test_swebench_checker.py`)

```python
def _mk_run(tmp_path, campaign="f-dev", case="django__django-99999",
            rerun=1, with_diff=True):
    run_dir = tmp_path / "artifacts" / campaign / f"{campaign}--{case}--r{rerun}"
    (run_dir / "files").mkdir(parents=True)
    if with_diff:
        (run_dir / "files" / "fix.diff").write_text(DIFF, encoding="utf-8")
    (run_dir / "verdict.json").write_text("{\"sentinel\": 1}",
                                          encoding="utf-8")
    return run_dir


def _spec_file(tmp_path):
    import json as _json
    p = tmp_path / "swebench_spec.json"
    p.write_text(_json.dumps(SPEC), encoding="utf-8")
    return p


def test_run_checker_happy_path(tmp_path):
    from eval.swebench_checker import run_checker
    run_dir = _mk_run(tmp_path)
    spec_path = _spec_file(tmp_path)

    def fake_runner(image, script, fix_diff, test_patch, timeout):
        assert "conda activate testbed" in script
        return {"log": _log("test_a (foo.tests.FooTest) ... ok\n"
                            "test_b (foo.tests.FooTest) ... ok"),
                "exit": 0}

    rc, out = run_checker(
        case="django__django-99999", rerun=1, campaign="f-dev",
        artifacts=str(tmp_path / "artifacts"), image="img:x",
        spec_path=str(spec_path), timeout=60, runner=fake_runner)
    assert rc == 0 and out["resolved"] is True
    import json as _json
    written = _json.loads((run_dir / "swebench_eval.json")
                          .read_text(encoding="utf-8"))
    assert written["resolved"] is True
    assert written["image"] == "img:x"
    assert (run_dir / "files" / "swebench_test_output.log").is_file()
    # verdict.json TIDAK disentuh (boundary — aturan inti spec)
    assert (run_dir / "verdict.json").read_text(encoding="utf-8") == (
        "{\"sentinel\": 1}")


def test_run_checker_missing_diff(tmp_path):
    from eval.swebench_checker import run_checker
    _mk_run(tmp_path, with_diff=False)
    rc, out = run_checker(
        case="django__django-99999", rerun=1, campaign="f-dev",
        artifacts=str(tmp_path / "artifacts"), image="img:x",
        spec_path=str(_spec_file(tmp_path)), timeout=60,
        runner=lambda *a, **k: {"log": "", "exit": 0})
    assert rc == 1 and "fix.diff" in out["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_swebench_checker.py -v`
Expected: 2 test baru FAIL `ImportError: cannot import name 'run_checker'`; 6 test lama tetap pass.

- [ ] **Step 3: Write implementation** (tambahkan di `eval/swebench_checker.py`)

```python
def run_checker(case: str, rerun: int, campaign: str, artifacts: str,
                image: str, spec_path: str, timeout: int,
                runner=None) -> tuple[int, dict]:
    from datetime import datetime, timezone
    from eval.swebench_runner import run_eval_in_container
    runner = runner or run_eval_in_container
    run_dir = (Path(artifacts) / campaign / f"{campaign}--{case}--r{rerun}")
    diff_path = run_dir / "files" / "fix.diff"
    if not diff_path.is_file():
        return 1, {"error": "fix.diff not found", "run_dir": str(run_dir)}
    try:
        spec = load_spec(Path(spec_path))
    except (FileNotFoundError, ValueError) as e:
        return 1, {"error": str(e)}
    fix_diff = diff_path.read_text(encoding="utf-8")
    res = runner(image, build_eval_script(spec), fix_diff,
                 spec["test_patch"], timeout)
    log_path = run_dir / "files" / "swebench_test_output.log"
    log_path.write_text(res["log"], encoding="utf-8", newline="\n")
    raw = grade_log(spec, fix_diff, log_path)
    summary = summarize_report(
        raw, spec, case=case, rerun=rerun, image=image, spec_path=spec_path,
        log_rel="files/swebench_test_output.log",
        checked_at=datetime.now(timezone.utc).isoformat())
    (run_dir / "swebench_eval.json").write_bytes(
        (json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
        .encode("utf-8"))
    return 0, summary


def main(argv: list[str] | None = None) -> int:
    import argparse
    from eval.swebench_runner import default_image
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--rerun", type=int, required=True)
    ap.add_argument("--campaign", default="f-dev")
    ap.add_argument("--artifacts", default="../artifacts")
    ap.add_argument("--image", default=None)
    ap.add_argument("--spec", default=None)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args(argv)
    rc, out = run_checker(
        case=args.case, rerun=args.rerun, campaign=args.campaign,
        artifacts=args.artifacts,
        image=args.image or default_image(args.case),
        spec_path=args.spec or f"cases/gold/{args.case}/swebench_spec.json",
        timeout=args.timeout)
    print(json.dumps(out, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_swebench_checker.py -v` lalu `python -m pytest -q`
Expected: 8 passed; suite penuh hijau.

- [ ] **Step 5: Commit**

Pesan: `feat(eval): CLI swebench_checker — swebench_eval.json kaya + log mentah di run dir` (+ trailer).

---

### Task 7: Dashboard — status 2-lapisan di `case_status` + panel ringkasan

**Files:**
- Modify: `ui/server.py` — `case_status()` (~baris 321), `stage_summary()` (~366), `render_stage_summary()` (~407), `_STYLE` (~520)
- Test: `tests/test_ui_two_layer.py` (baru)

**Interfaces:**
- Consumes: `swebench_eval.json` (skema Task 4 §5).
- Produces: `read_swebench_eval(run_dir: Path) -> dict | None`; `case_status()` kini bisa mengembalikan `status` ∈ `{"PASS","FAIL","WAIT","ANOMALY","?"}` (dua nilai baru utk kampanye `f-*`); `stage_summary()` dict bertambah kunci `"wait"` dan `"anomaly"`; render menampilkan keduanya. Definisi (spec §6): PASS = `pass_l1` ∧ `resolved`; product-pass tanpa eval = WAIT ⏳ (BUKAN FAIL — menutup known issue flip→FAIL); product FAIL + `resolved=true` = ANOMALY ⚠️.

- [ ] **Step 1: Write the failing tests**

```python
"""Test status 2-lapisan dashboard (spec §6) — kampanye f-*."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))
import server  # noqa: E402


def _mk_run(tmp_path, verdict="flip", pass_l1=True, swebench=None,
            rerun=1):
    run_dir = tmp_path / "f-dev" / f"f-dev--django__django-1--r{rerun}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "verdict.json").write_text(json.dumps(
        {"phases": {"fix": {"verdict": verdict}}, "wall": None,
         "pass_l1": pass_l1}), encoding="utf-8")
    if swebench is not None:
        (run_dir / "swebench_eval.json").write_text(
            json.dumps(swebench), encoding="utf-8")
    return run_dir


def test_pass_when_both_layers_pass(tmp_path):
    rd = _mk_run(tmp_path, swebench={"resolved": True})
    st = server.case_status("f-dev", rd)
    assert st["status"] == "PASS"


def test_wait_when_no_swebench_eval(tmp_path):
    rd = _mk_run(tmp_path, swebench=None)
    st = server.case_status("f-dev", rd)
    assert st["status"] == "WAIT"
    assert "VERIFY" in st["category"]


def test_fail_verify_lists_regressions(tmp_path):
    rd = _mk_run(tmp_path, swebench={
        "resolved": False, "patch_successfully_applied": True,
        "f2p_failed": [], "p2p_failed": ["test_x (a.B)"]})
    st = server.case_status("f-dev", rd)
    assert st["status"] == "FAIL"
    assert st["category"] == "verify-fail"
    assert any("test_x (a.B)" in r for r in st["reasons"])


def test_anomaly_product_fail_but_resolved(tmp_path):
    rd = _mk_run(tmp_path, verdict="no-flip", pass_l1=False,
                 swebench={"resolved": True})
    st = server.case_status("f-dev", rd)
    assert st["status"] == "ANOMALY"


def test_product_fail_plain_stays_fail(tmp_path):
    rd = _mk_run(tmp_path, verdict="no-flip", pass_l1=False, swebench=None)
    st = server.case_status("f-dev", rd)
    assert st["status"] == "FAIL"


def test_stage_summary_counts_new_states(tmp_path):
    _mk_run(tmp_path, rerun=1, swebench={"resolved": True})
    runs = [{"run_id": "f-dev--django__django-1--r1"}]
    s = server.stage_summary(tmp_path / "f-dev", "f-dev", runs)
    assert s["pass"] == 1 and s["wait"] == 0 and s["anomaly"] == 0
    html_out = server.render_stage_summary(s)
    assert "PASS 1" in html_out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ui_two_layer.py -v`
Expected: FAIL — `case_status` sekarang mengembalikan FAIL utk verdict flip (known issue) & belum ada status WAIT/ANOMALY; `stage_summary` belum punya kunci wait/anomaly.

- [ ] **Step 3: Implement**

3a. Tambah helper di `ui/server.py` (dekat `_wrong_file_reasons`, ~baris 302):

```python
def read_swebench_eval(run_dir: Path) -> dict | None:
    """swebench_eval.json (checker L2 realm dev) — None bila absen/rusak."""
    p = Path(run_dir) / "swebench_eval.json"
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _fix_verify_status(vtext: str, vj: dict, run_dir: Path) -> dict | None:
    """Status 2-lapisan kampanye f-* (spec checker L2 §6). None -> alur lama.

    PASS = pass_l1 (product, flip) AND resolved (SWE-bench checker).
    Product-pass tanpa eval = WAIT (bukan FAIL palsu). Product FAIL tapi
    resolved=true = ANOMALY (kontradiksi sinyal, flag menonjol)."""
    sw = read_swebench_eval(run_dir)
    resolved = sw.get("resolved") if sw else None
    product_pass = vtext == "flip" and vj.get("pass_l1") is True
    if product_pass and resolved is True:
        return {"status": "PASS", "category": "pass (L1+L2)", "reasons": []}
    if product_pass and resolved is False:
        reasons = []
        if sw.get("f2p_failed"):
            reasons.append("F2P gagal: " + ", ".join(
                str(t) for t in sw["f2p_failed"][:5]))
        if sw.get("p2p_failed"):
            reasons.append("regresi P2P: " + ", ".join(
                str(t) for t in sw["p2p_failed"][:5]))
        if not sw.get("patch_successfully_applied", True):
            reasons.append("patch/test_patch gagal apply di dunia VERIFY")
        return {"status": "FAIL", "category": "verify-fail",
                "reasons": reasons or ["resolved=false tanpa detail"]}
    if product_pass:
        return {"status": "WAIT", "category": "product-pass, menunggu VERIFY",
                "reasons": ["swebench_eval.json belum ada — jalankan "
                            "python -m eval.swebench_checker"]}
    if resolved is True:
        return {"status": "ANOMALY",
                "category": "anomaly: product FAIL tapi SWE-bench resolved",
                "reasons": [f"verdict product: {vtext} — kontradiksi sinyal, "
                            "autopsi manual"]}
    return None  # product fail biasa -> alur lama (exit_fails dst.)
```

3b. Di `case_status()`, SETELAH baris `vtext, icon = merge_gold_verdict(...)` (~339), sisipkan:

```python
    if campaign.startswith("f-"):
        two = _fix_verify_status(vtext, vj, run_dir)
        if two is not None:
            return two
```

3c. Di `stage_summary()` return dict (~396), tambah dua kunci (dan WAIT/ANOMALY ikut dilaporkan dari run TERBARU — case WAIT tak boleh dihitung FAIL):

```python
    return {"total": len(items),
            "pass": sum(1 for i in items if i["status"] == "PASS"),
            "fail": sum(1 for i in items if i["status"] == "FAIL"),
            "wait": sum(1 for i in items if i["status"] == "WAIT"),
            "anomaly": sum(1 for i in items if i["status"] == "ANOMALY"),
            "unknown": sum(1 for i in items if i["status"] == "?"),
            "items": items}
```

3d. Di `render_stage_summary()`: head tambah segmen bila >0 (`WAIT n` dgn ⏳, `ANOMALY n` dgn ⚠️); bar tambah kelas `.sw` (WAIT, `#8a6d1a`) dan `.sa` (ANOMALY, `#7b1fa2`) di `_STYLE`; tabel "rincian" (variabel `problems`) memasukkan status `("FAIL", "ANOMALY", "?")`; case WAIT masuk collapsible sendiri `menunggu VERIFY (n)` berisi case+run+mulai.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ui_two_layer.py -v` lalu `python -m pytest -q`
Expected: 6 passed; suite penuh hijau — perhatikan `tests/test_ui_summary.py` lama TIDAK boleh pecah (kunci dict lama tetap ada).

- [ ] **Step 5: Commit**

Pesan: `feat(ui): status 2-lapisan f-dev — PASS=L1∧L2, WAIT, ANOMALY; tutup bug flip→FAIL` (+ trailer).

---

### Task 8: Dashboard — label tab "FIX and VERIFY" + seksi VERIFY di halaman run

**Files:**
- Modify: `ui/server.py` — `_CAMPAIGN_LABELS`/`_PIPELINE_STAGES` (~baris 96-104), `page_run()` (~663)
- Test: `tests/test_ui_two_layer.py` (tambah)

**Interfaces:**
- Consumes: `read_swebench_eval` (Task 7), `gold_eval.json` (ada), `verdict.json`.
- Produces: `campaign_label("f-dev") == "FIX and VERIFY"`; tidak ada tab `v-dev` (TANPA tab keempat — keputusan Mirza); `page_run()` utk kampanye `f-*` menampilkan seksi `VERIFY (SWE-bench)` + `gold-match (advisory)` + tail log VERIFY.

- [ ] **Step 1: Write the failing tests** (tambah di `tests/test_ui_two_layer.py`)

```python
def test_tab_label_fix_and_verify_no_fourth_tab():
    assert server.campaign_label("f-dev") == "FIX and VERIFY"
    assert "v-dev" not in server.with_stage_tabs(["r-dev"])


def test_page_run_shows_verify_sections(tmp_path):
    rd = _mk_run(tmp_path, swebench={
        "resolved": True, "patch_successfully_applied": True,
        "f2p_passed": ["test_a (a.B)"], "f2p_failed": [],
        "p2p_passed_count": 7, "p2p_failed": [],
        "log": "files/swebench_test_output.log"})
    (rd / "gold_eval.json").write_text(json.dumps(
        {"touched_files": ["x.py"], "gold_files": ["x.py"],
         "file_match": True, "line_overlap": True}), encoding="utf-8")
    (rd / "files").mkdir(exist_ok=True)
    (rd / "files" / "swebench_test_output.log").write_text(
        "test_a (a.B) ... ok\n", encoding="utf-8")
    html_out = server.page_run(tmp_path, "f-dev",
                               "f-dev--django__django-1--r1", 200)
    assert "VERIFY (SWE-bench)" in html_out
    assert "resolved" in html_out
    assert "gold-match (advisory)" in html_out
    assert "swebench_test_output.log" in html_out


def test_page_run_verify_waiting_note(tmp_path):
    _mk_run(tmp_path, swebench=None)
    html_out = server.page_run(tmp_path, "f-dev",
                               "f-dev--django__django-1--r1", 200)
    assert "menunggu VERIFY" in html_out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ui_two_layer.py -v`
Expected: 3 test baru FAIL (label masih "FIX"; seksi VERIFY belum ada).

- [ ] **Step 3: Implement**

3a. Ubah peta label & pipeline (baris ~96-104):

```python
_CAMPAIGN_LABELS = {"r-dev": "REPRODUCE", "l-dev": "LOCALIZE",
                    "f-dev": "FIX and VERIFY"}
```

dan keluarkan `"v-dev"` dari `_PIPELINE_STAGES` (checker L2 = pekerjaan VERIFY di dalam tab FIX and VERIFY; tanpa tab keempat — keputusan Mirza 2026-07-20). Struktur/urutan tab lain TIDAK berubah.

3b. Di `page_run()`, setelah blok verdict (~688) tambahkan utk `campaign.startswith("f-")`:

```python
    if campaign.startswith("f-"):
        sw = read_swebench_eval(run_dir)
        parts.append("<h2>VERIFY (SWE-bench)</h2>")
        if sw is None:
            parts.append("<p class='dim'>product-pass, menunggu VERIFY — "
                         "swebench_eval.json belum ada (jalankan "
                         "python -m eval.swebench_checker)</p>")
        else:
            ok = "✅" if sw.get("resolved") else "❌"
            parts.append(
                f"<p>resolved: {ok} {html.escape(str(sw.get('resolved')))} | "
                f"apply: {html.escape(str(sw.get('patch_successfully_applied')))} | "
                f"F2P lulus {len(sw.get('f2p_passed') or [])} / gagal "
                f"{len(sw.get('f2p_failed') or [])} | P2P lulus "
                f"{sw.get('p2p_passed_count', '?')} / regresi "
                f"{len(sw.get('p2p_failed') or [])}</p>")
            for label, key in (("F2P gagal", "f2p_failed"),
                               ("regresi P2P", "p2p_failed")):
                if sw.get(key):
                    items = "".join(f"<li>{html.escape(str(t))}</li>"
                                    for t in sw[key])
                    parts.append(f"<p>{label}:</p><ul>{items}</ul>")
        gpath = run_dir / "gold_eval.json"
        parts.append("<h2>gold-match (advisory)</h2>")
        if gpath.is_file():
            try:
                g = json.loads(gpath.read_text(encoding="utf-8"))
                parts.append(
                    f"<p class='dim'>file_match: {g.get('file_match')} | "
                    f"line_overlap: {g.get('line_overlap')} | touched: "
                    f"{html.escape(', '.join(g.get('touched_files') or []))} "
                    f"vs gold: "
                    f"{html.escape(', '.join(g.get('gold_files') or []))}</p>")
            except (OSError, ValueError):
                parts.append("<p class='dim'>gold_eval.json rusak</p>")
        else:
            parts.append("<p class='dim'>(gold_eval.json belum ada)</p>")
        swlog = tail_lines(run_dir / "files" / "swebench_test_output.log", n)
        if swlog:
            parts.append(f"<h2>swebench_test_output.log (tail {n})</h2>")
            parts.append("<pre>" + html.escape("\n".join(swlog)) + "</pre>")
```

Anomaly flag di halaman run: bila `sw` ada, `sw.get("resolved") is True`, dan verdict product bukan flip → sisipkan `<p>⚠️ ANOMALY: product FAIL tapi SWE-bench resolved — autopsi manual</p>` tepat di bawah `<h2>VERIFY (SWE-bench)</h2>`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ui_two_layer.py -v` lalu `python -m pytest -q`
Expected: 9 passed di file ini; suite penuh hijau.

- [ ] **Step 5: Commit**

Pesan: `feat(ui): tab FIX and VERIFY + seksi detail VERIFY/gold-match di halaman run` (+ trailer).

---

### Task 9: Freeze 13 spec + re-eval resmi 13660 + dokumentasi

**Files:**
- Create (via CLI Task 2): `cases/gold/<13 case>/swebench_spec.json`
- Modify: `README.md` (blok "Aturan status 2-lapisan" + known issue + invokasi), vault `F-dev Log — fase FIX` (blok baru), vault `Desain SWE-bench Checker L2 — Keputusan Brainstorm` (status eksekusi)

**Interfaces:**
- Consumes: seluruh task sebelumnya.

- [ ] **Step 1: Freeze spec 13 case populasi f-dev** (daftar dari spec FIX §9)

Run (dari root `main\`):

```
python -m eval.fetch_swebench_spec --case django__django-11422 --case django__django-11999 --case django__django-12308 --case django__django-13401 --case django__django-13220 --case django__django-11964 --case django__django-11910 --case django__django-13660 --case django__django-14017 --case django__django-15400 --case astropy__astropy-7746 --case django__django-13768 --case django__django-12747
```

Expected: 13 baris JSON `{"case": ..., "spec": ...}`, rc 0. Verifikasi 13 file ada dan masing-masing punya `FAIL_TO_PASS` non-kosong.

- [ ] **Step 2: Commit spec beku**

Pesan: `data: freeze swebench_spec.json 13 case f-dev (SWE-bench Lite)` (+ trailer).

- [ ] **Step 3: Re-eval resmi run 13660 r1** (docker nyata)

Run: `python -m eval.swebench_checker --case django__django-13660 --rerun 1`
Expected: exit 0; `../artifacts/f-dev/f-dev--django__django-13660--r1/swebench_eval.json` berisi `resolved` (dugaan true — apapun hasilnya adalah data) + `files/swebench_test_output.log` ada. `verdict.json` run TIDAK berubah (cek `git`-less: bandingkan mtime/isi sebelum-sesudah).

- [ ] **Step 4: Verifikasi dashboard nyata**

Restart viewer (dari `main\`): `Start-Process -WindowStyle Hidden python -ArgumentList 'ui\server.py','--root','..\artifacts','--port','8766'` lalu buka `http://127.0.0.1:8766/?tab=f-dev`.
Expected: tab berlabel "FIX and VERIFY"; run 13660 r1 = PASS (bila resolved=true) di panel; halaman run menampilkan seksi VERIFY (SWE-bench) + gold-match advisory + tail log. Ambil screenshot utk laporan Mirza.

- [ ] **Step 5: Update README + vault, commit dokumentasi**

- README: tandai aturan 2-lapisan TERIMPLEMENTASI (checker: invokasi `python -m eval.fetch_swebench_spec` + `python -m eval.swebench_checker`), hapus/tutup blok "KNOWN ISSUE dashboard" (bug flip→FAIL selesai), sebut tab "FIX and VERIFY", sebut 5 state status (PASS/FAIL/verify-fail/WAIT/ANOMALY) dan file `swebench_eval.json`.
- Vault `F-dev Log`: blok "Checker L2 live" — hasil probe + hasil re-eval 13660 (resolved?, durasi, temuan).
- Vault `Desain SWE-bench Checker L2`: tambah seksi status "Eksekusi selesai <tanggal> — commit range".
- Commit: `docs: README + log checker L2 live; re-eval 13660 & dashboard 2-lapisan terverifikasi` (+ trailer).

- [ ] **Step 6: Lapor Mirza via Telegram** — ringkasan hasil akhir (jumlah test suite, hasil re-eval 13660, screenshot dashboard) + tawaran next step (eval 12 case sisa saat run FIX-nya ada).

---

## Self-review (sudah dijalankan penulis plan)

- **Spec coverage:** §2 arsitektur → Task 1/4/5/6; §3 data beku → Task 2 + 9; §4 alur → Task 4-6; §5 skema kaya → Task 4 (`summarize_report`) + test; §6 dashboard (5 state, disambiguasi, tab, detail) → Task 7-8; §7 gold_eval dipertahankan → tidak ada task penghapusan + tampil advisory (Task 8); §8 urutan (probe dulu) → Task 3 sebelum core final; §9 testing → tiap task TDD, nol docker di suite; §10 non-goals dihormati (tanpa pipeline auto, tanpa perubahan kontrak).
- **Placeholder scan:** semua step berisi kode/perintah konkret; tidak ada TBD.
- **Type consistency:** `run_checker(runner=...)` signature konsisten dgn `run_eval_in_container(image, eval_script, fix_diff, test_patch, timeout)`; `summarize_report` dipanggil dgn kwargs yang sama di Task 4 test & Task 6 impl; kunci `swebench_eval.json` identik di Task 4/6/7/8 (`resolved`, `patch_successfully_applied`, `f2p_passed/f2p_failed`, `p2p_passed_count/p2p_failed`).
- **Risiko diketahui:** (a) probe Task 3 bisa mematahkan template skrip — plan MEWAJIBKAN penyesuaian Task 4 sebelum lanjut; (b) `make_test_spec` pada spec sintetis test mungkin menuntut field tambahan — fixture sudah menyertakan `environment_setup_commit`; bila masih KeyError, tambahkan field kosong ke fixture SPEC (bukan ke skema produksi); (c) durasi run test P2P django bisa menit-an — default `--timeout 3600`.
