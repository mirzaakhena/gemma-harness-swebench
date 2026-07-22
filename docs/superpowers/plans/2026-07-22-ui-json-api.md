# API JSON UI Log Viewer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Endpoint JSON read-only (`/api/campaigns`, `/api/runs`, `/api/cases`) di `ui/server.py` supaya agent bisa membaca data harness tanpa parse HTML, plus dokumen referensi API untuk agent di sesi lain.

**Architecture:** Route `/api/*` ditambahkan ke server HTML yang sudah ada, memakai ulang fungsi inti (`list_runs`, `case_status`, `stage_summary`, `filter_runs_by_case`, `paginate`). Fungsi serialisasi API murni (dict-in dict-out) dites unit; layer HTTP dites integrasi dengan `ThreadingHTTPServer` port 0.

**Tech Stack:** Python 3.12 stdlib only, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-ui-json-api-design.md`

## Global Constraints

- Stdlib only (Python 3.12) — TANPA dependensi baru.
- Read-only mutlak: viewer tidak pernah menulis ke `artifacts/`.
- Semua kerja di `/Users/mirza/Workspace/gemma-harness-swebench/main` (repo git; branch `main`).
- Jalankan pytest dari direktori `main/`: `python3 -m pytest tests/ -q`.
- SETIAP commit wajib membawa trailer `Agent: claude-code` (hook `commit-trailer-guard` menolak commit tanpanya).
- Gaya kode mengikuti `ui/server.py`: komentar Bahasa Indonesia, fail-soft (jangan crash pada file rusak/absen), baris ≤ 79 char.
- Enum status API: `PASS`, `FAIL`, `WAIT`, `ANOMALY`, `?` (persis `case_status()`).

---

### Task 1: Helper `run_index_verdict` (ekstraksi dari `page_index`)

`page_index` (ui/server.py:965-984) membangun teks verdict gabungan inline. API butuh logika yang sama; ekstrak jadi helper supaya tidak drift.

**Files:**
- Modify: `ui/server.py` (tambah fungsi setelah `index_row_verdict`, ~line 856; refactor `page_index` ~line 965-984)
- Test: `tests/test_ui_api.py` (file baru)

**Interfaces:**
- Consumes: `index_row_verdict(phases, wall)`, `merge_gold_verdict(vtext, icon, campaign, run_dir)` (sudah ada).
- Produces: `run_index_verdict(campaign: str, run_dir: Path) -> tuple[str, str]` — `(vtext, icon)`; verdict.json absen → `("-", "")`; rusak → `("(verdict.json rusak)", "")`. Dipakai Task 3.

- [ ] **Step 1: Tulis failing test**

Buat `tests/test_ui_api.py`:

```python
"""Test API JSON UI log viewer (ui/server.py) — serialisasi + HTTP layer."""
import json

from ui.server import run_index_verdict


# --- fixture artifacts sintetis ---------------------------------------------

def mk_run(root, campaign, case, rerun, verdict=None, pass_l1=None,
           started="2026-07-21T14:03:00+07:00"):
    """Satu run sintetis: dir + events.jsonl + runs.jsonl (+ verdict.json).

    verdict None -> run hidup tanpa verdict.json.
    """
    camp = root / campaign
    run_id = f"{campaign}--{case}--{rerun}"
    rd = camp / run_id
    rd.mkdir(parents=True)
    (rd / "events.jsonl").write_text(
        json.dumps({"ts": started, "event": "start"}) + "\n",
        encoding="utf-8")
    with (camp / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"run_id": run_id, "event": "start"}) + "\n")
        if verdict is not None:
            f.write(json.dumps({"run_id": run_id, "event": "end",
                                "verdict": verdict, "wall": 12.3}) + "\n")
    if verdict is not None:
        vj = {"phases": {"reproduce": {"verdict": verdict}},
              "started": started, "finished": started}
        if pass_l1 is not None:
            vj["pass_l1"] = pass_l1
        (rd / "verdict.json").write_text(json.dumps(vj), encoding="utf-8")
    return run_id


# --- run_index_verdict ------------------------------------------------------

def test_run_index_verdict_missing_verdict(tmp_path):
    assert run_index_verdict("r-dev", tmp_path) == ("-", "")


def test_run_index_verdict_broken_verdict(tmp_path):
    (tmp_path / "verdict.json").write_text("{rusak", encoding="utf-8")
    text, icon = run_index_verdict("r-dev", tmp_path)
    assert text == "(verdict.json rusak)" and icon == ""


def test_run_index_verdict_pass(tmp_path):
    rid = mk_run(tmp_path, "r-dev", "django__django-1", "r1",
                 verdict="pass", pass_l1=True)
    text, icon = run_index_verdict("r-dev", tmp_path / "r-dev" / rid)
    assert text == "pass" and icon.startswith("✅")


def test_run_index_verdict_merges_gold_wrong_file(tmp_path):
    rid = mk_run(tmp_path, "l-dev", "django__django-1", "r1", verdict="pass")
    run_dir = tmp_path / "l-dev" / rid
    (run_dir / "gold_eval.json").write_text(
        json.dumps({"qualified": False}), encoding="utf-8")
    text, icon = run_index_verdict("l-dev", run_dir)
    assert text == "wrong-file" and icon.startswith("❌")
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `cd /Users/mirza/Workspace/gemma-harness-swebench/main && python3 -m pytest tests/test_ui_api.py -q`
Expected: FAIL — `ImportError: cannot import name 'run_index_verdict'`

- [ ] **Step 3: Implementasi helper + refactor page_index**

Di `ui/server.py`, tambah setelah `index_row_verdict` (setelah ~line 855):

```python
def run_index_verdict(campaign: str, run_dir: Path) -> tuple[str, str]:
    """(vtext, ikon) kolom verdict tabel index utk SATU run — verdict L1
    gabungan + merge gold_eval (dipakai page_index DAN /api/runs supaya
    tak drift). verdict.json absen -> ("-", ""); rusak -> teks rusak."""
    vpath = Path(run_dir) / "verdict.json"
    if not vpath.is_file():
        return "-", ""
    try:
        vj = json.loads(vpath.read_text(encoding="utf-8"))
        phases = {k: (p or {}).get("verdict")
                  for k, p in (vj.get("phases") or {}).items()}
        vtext, icon = index_row_verdict(phases, vj.get("wall"))
        return merge_gold_verdict(vtext, icon, campaign, Path(run_dir))
    except (ValueError, OSError, AttributeError):
        return "(verdict.json rusak)", ""
```

Refactor `page_index` — blok lama (~line 966-984):

```python
        vpath = root / active / rid / "verdict.json"
        vtext, icon = "-", ""
        if vpath.is_file():
            try:
                vj = json.loads(vpath.read_text(encoding="utf-8"))
                phases = {k: (p or {}).get("verdict")
                          for k, p in (vj.get("phases") or {}).items()}
                vtext, icon = index_row_verdict(phases, vj.get("wall"))
                vtext, icon = merge_gold_verdict(vtext, icon, active,
                                                 root / active / rid)
                if active.startswith("f-"):
                    # ikon baris disinkronkan ke status 2-lapisan (spec §6)
                    # — teks verdict TETAP vonis L1 produk apa adanya
                    # (permintaan Mirza: viewer verify-fail jangan lagi ✅).
                    two_status = case_status(active, root / active / rid)
                    icon = status_icon(two_status["status"])
            except (ValueError, OSError, AttributeError):
                vtext = "(verdict.json rusak)"
```

diganti menjadi:

```python
        vpath = root / active / rid / "verdict.json"
        vtext, icon = run_index_verdict(active, root / active / rid)
        if vpath.is_file() and active.startswith("f-"):
            # ikon baris disinkronkan ke status 2-lapisan (spec §6)
            # — teks verdict TETAP vonis L1 produk apa adanya
            # (permintaan Mirza: viewer verify-fail jangan lagi ✅).
            two_status = case_status(active, root / active / rid)
            icon = status_icon(two_status["status"])
```

CATATAN perilaku yang HARUS dipertahankan: pada verdict.json rusak, kode lama membiarkan `icon = ""` — helper baru juga mengembalikan `("(verdict.json rusak)", "")`, jadi setara.

- [ ] **Step 4: Jalankan test baru + regresi**

Run: `python3 -m pytest tests/test_ui_api.py tests/test_ui_core.py -q`
Expected: semua PASS (test lama page_index jadi jaring regresi refactor).

- [ ] **Step 5: Commit**

```bash
git add ui/server.py tests/test_ui_api.py
git commit -m "refactor(ui): ekstrak run_index_verdict dari page_index (persiapan API JSON)

Agent: claude-code"
```

---

### Task 2: `api_campaigns`

**Files:**
- Modify: `ui/server.py` (seksi baru `# --- API JSON ---` sebelum `# --- rendering HTML ---`, ~line 697)
- Test: `tests/test_ui_api.py`

**Interfaces:**
- Consumes: `order_campaigns`, `with_stage_tabs`, `list_campaigns`, `campaign_label`, `campaign_phase` (sudah ada).
- Produces: `api_campaigns(root: Path) -> dict` — `{"campaigns": [{"name", "label", "phase"}]}`. Dipakai Task 5.

- [ ] **Step 1: Tulis failing test** (append ke `tests/test_ui_api.py`)

```python
# --- api_campaigns ----------------------------------------------------------

def test_api_campaigns_pipeline_order_and_labels(tmp_path):
    from ui.server import api_campaigns
    (tmp_path / "r-dev").mkdir()
    (tmp_path / "z-lain").mkdir()
    out = api_campaigns(tmp_path)
    names = [c["name"] for c in out["campaigns"]]
    # stage pipeline selalu tampil (walau dir belum ada), urut pipeline;
    # kampanye non-pipeline menyusul
    assert names == ["r-dev", "l-dev", "f-dev", "z-lain"]
    assert out["campaigns"][0] == {"name": "r-dev", "label": "REPRODUCE",
                                   "phase": "R"}
    assert out["campaigns"][2]["label"] == "FIX and VERIFY"
    assert out["campaigns"][3] == {"name": "z-lain", "label": "z-lain",
                                   "phase": ""}


def test_api_campaigns_empty_root(tmp_path):
    from ui.server import api_campaigns
    names = [c["name"] for c in api_campaigns(tmp_path)["campaigns"]]
    assert names == ["r-dev", "l-dev", "f-dev"]
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `python3 -m pytest tests/test_ui_api.py -q`
Expected: FAIL — `ImportError: cannot import name 'api_campaigns'`

- [ ] **Step 3: Implementasi**

Di `ui/server.py`, buat seksi baru tepat SEBELUM `# --- rendering HTML ---`:

```python
# --- API JSON (kontrak: docs/api-ui-viewer.md) -------------------------------
# Read-only, paritas semantik dengan UI HTML: status per run/case dihitung
# lewat jalur logika yang SAMA (case_status, stage_summary, dst.).

_API_STATUSES = ("PASS", "FAIL", "WAIT", "ANOMALY", "?")


def api_campaigns(root: Path) -> dict:
    """Payload /api/campaigns: daftar kampanye urut pipeline, paritas tab
    UI (stage pipeline tampil walau direktorinya belum ada)."""
    campaigns = order_campaigns(with_stage_tabs(list_campaigns(root)))
    return {"campaigns": [{"name": c, "label": campaign_label(c),
                           "phase": campaign_phase(c)} for c in campaigns]}
```

- [ ] **Step 4: Jalankan test, pastikan pass**

Run: `python3 -m pytest tests/test_ui_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/server.py tests/test_ui_api.py
git commit -m "feat(ui): api_campaigns - daftar kampanye JSON urut pipeline

Agent: claude-code"
```

---

### Task 3: `api_runs`

**Files:**
- Modify: `ui/server.py` (seksi API JSON, setelah `api_campaigns`)
- Test: `tests/test_ui_api.py`

**Interfaces:**
- Consumes: `sort_runs_desc`, `list_runs`, `filter_runs_by_case`, `split_run_id`, `case_status`, `run_index_verdict` (Task 1), `run_started_str`, `paginate`, `PAGE_SIZE`.
- Produces: `api_runs(root: Path, campaign: str, status: str | None = None, q: str | None = None, page: int = 1, per_page: int = PAGE_SIZE) -> dict`. Dipakai Task 5.

- [ ] **Step 1: Tulis failing test** (append ke `tests/test_ui_api.py`)

```python
# --- api_runs ---------------------------------------------------------------

def test_api_runs_fields_and_order(tmp_path):
    from ui.server import api_runs
    mk_run(tmp_path, "r-dev", "django__django-1", "r1",
           verdict="pass", pass_l1=True,
           started="2026-07-20T10:00:00+07:00")
    mk_run(tmp_path, "r-dev", "sympy__sympy-2", "r1",
           verdict="wrong-logic",
           started="2026-07-21T14:03:00+07:00")
    out = api_runs(tmp_path, "r-dev")
    assert out["campaign"] == "r-dev"
    assert out["total"] == 2 and out["total_pages"] == 1
    # urut started desc: run terbaru dulu
    assert [r["case"] for r in out["runs"]] == \
        ["sympy__sympy-2", "django__django-1"]
    fail = out["runs"][0]
    assert fail["rerun"] == "r1"
    assert fail["verdict"] == "wrong-logic"
    assert fail["status"] == "FAIL" and fail["category"] == "wrong-logic"
    assert fail["wall"] == 12.3
    assert fail["started"] == "2026-07-21 14:03"
    ok = out["runs"][1]
    assert ok["status"] == "PASS" and ok["verdict"] == "pass"


def test_api_runs_filter_status_and_q(tmp_path):
    from ui.server import api_runs
    mk_run(tmp_path, "r-dev", "django__django-1", "r1",
           verdict="pass", pass_l1=True)
    mk_run(tmp_path, "r-dev", "django__django-1", "r2",
           verdict="wrong-logic")
    mk_run(tmp_path, "r-dev", "sympy__sympy-2", "r1",
           verdict="wrong-logic")
    out = api_runs(tmp_path, "r-dev", status="FAIL")
    assert out["total"] == 2
    assert all(r["status"] == "FAIL" for r in out["runs"])
    out = api_runs(tmp_path, "r-dev", status="FAIL", q="django")
    assert out["total"] == 1
    assert out["runs"][0]["run_id"] == "r-dev--django__django-1--r2"


def test_api_runs_paging_clamps(tmp_path):
    from ui.server import api_runs
    for i in range(4):
        mk_run(tmp_path, "r-dev", f"case-{i}", "r1",
               verdict="pass", pass_l1=True)
    out = api_runs(tmp_path, "r-dev", page=99, per_page=3)
    assert out["total"] == 4 and out["total_pages"] == 2
    assert out["page"] == 2 and len(out["runs"]) == 1


def test_api_runs_unknown_campaign_empty(tmp_path):
    from ui.server import api_runs
    out = api_runs(tmp_path, "tidak-ada")
    assert out["runs"] == [] and out["total"] == 0


def test_api_runs_run_without_verdict_is_unknown(tmp_path):
    from ui.server import api_runs
    mk_run(tmp_path, "r-dev", "django__django-1", "r1")  # tanpa verdict
    out = api_runs(tmp_path, "r-dev")
    r = out["runs"][0]
    assert r["status"] == "?" and r["verdict"] == "-"
    assert r["category"] == "tanpa verdict.json"
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `python3 -m pytest tests/test_ui_api.py -q`
Expected: FAIL — `ImportError: cannot import name 'api_runs'`

- [ ] **Step 3: Implementasi** (setelah `api_campaigns`)

```python
def api_runs(root: Path, campaign: str, status: str | None = None,
             q: str | None = None, page: int = 1,
             per_page: int = PAGE_SIZE) -> dict:
    """Payload /api/runs: run individual sebuah kampanye, urut started desc
    (paritas tabel UI). status/category/reasons = case_status() run itu;
    verdict = teks gabungan kolom UI (run_index_verdict). `total` = jumlah
    run SETELAH filter status+q, sebelum paging."""
    campaign_dir = Path(root) / campaign
    runs = sort_runs_desc(list_runs(campaign_dir), campaign_dir)
    runs = filter_runs_by_case(runs, q)
    entries = []
    for r in runs:
        rid = r["run_id"]
        run_dir = campaign_dir / rid
        case_id, rerun = split_run_id(rid)
        st = case_status(campaign, run_dir)
        vtext, _ = run_index_verdict(campaign, run_dir)
        entries.append({"run_id": rid, "case": case_id, "rerun": rerun,
                        "verdict": vtext, "status": st["status"],
                        "category": st["category"],
                        "reasons": st["reasons"], "wall": r.get("wall"),
                        "started": run_started_str(run_dir)})
    if status is not None:
        entries = [e for e in entries if e["status"] == status]
    total = len(entries)
    page_items, total_pages = paginate(entries, page, per_page)
    return {"campaign": campaign, "page": max(1, min(page, total_pages)),
            "total_pages": total_pages, "total": total, "runs": page_items}
```

- [ ] **Step 4: Jalankan test, pastikan pass**

Run: `python3 -m pytest tests/test_ui_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/server.py tests/test_ui_api.py
git commit -m "feat(ui): api_runs - daftar run JSON dengan filter status/case + paging

Agent: claude-code"
```

---

### Task 4: `api_cases`

**Files:**
- Modify: `ui/server.py` (seksi API JSON, setelah `api_runs`)
- Test: `tests/test_ui_api.py`

**Interfaces:**
- Consumes: `list_runs`, `filter_runs_by_case`, `stage_summary`, `split_run_id`, `paginate`, `PAGE_SIZE`.
- Produces: `api_cases(root: Path, campaign: str, status: str | None = None, q: str | None = None, page: int = 1, per_page: int = PAGE_SIZE) -> dict`. Dipakai Task 5.
- Semantik `summary`: dihitung SETELAH filter `q` (konsisten panel UI yang menghitung dari run terfilter) tapi SEBELUM filter `status` dan paging — angka tak berubah saat pindah filter status/halaman.

- [ ] **Step 1: Tulis failing test** (append ke `tests/test_ui_api.py`)

```python
# --- api_cases --------------------------------------------------------------

def test_api_cases_ever_qualified_semantics(tmp_path):
    from ui.server import api_cases
    # case A: r1 gagal, r2 pass -> status case PASS (pernah qualified)
    mk_run(tmp_path, "r-dev", "case-A", "r1", verdict="wrong-logic",
           started="2026-07-20T10:00:00+07:00")
    mk_run(tmp_path, "r-dev", "case-A", "r2", verdict="pass", pass_l1=True,
           started="2026-07-21T10:00:00+07:00")
    # case B: hanya gagal
    mk_run(tmp_path, "r-dev", "case-B", "r1", verdict="wrong-logic")
    out = api_cases(tmp_path, "r-dev")
    assert out["summary"] == {"PASS": 1, "FAIL": 1, "WAIT": 0,
                              "ANOMALY": 0, "?": 0}
    by_id = {c["case_id"]: c for c in out["cases"]}
    assert by_id["case-A"]["status"] == "PASS"
    assert by_id["case-A"]["runs"] == 2
    assert by_id["case-B"]["status"] == "FAIL"
    assert by_id["case-B"]["category"] == "wrong-logic"
    assert by_id["case-B"]["latest_run"] == "r-dev--case-B--r1"


def test_api_cases_summary_stable_under_status_filter(tmp_path):
    from ui.server import api_cases
    mk_run(tmp_path, "r-dev", "case-A", "r1", verdict="pass", pass_l1=True)
    mk_run(tmp_path, "r-dev", "case-B", "r1", verdict="wrong-logic")
    out = api_cases(tmp_path, "r-dev", status="FAIL")
    # summary TIDAK berubah oleh filter status; daftar cases berubah
    assert out["summary"]["PASS"] == 1 and out["summary"]["FAIL"] == 1
    assert out["total"] == 1
    assert out["cases"][0]["case_id"] == "case-B"


def test_api_cases_q_filter_and_paging(tmp_path):
    from ui.server import api_cases
    for i in range(3):
        mk_run(tmp_path, "r-dev", f"django-{i}", "r1",
               verdict="pass", pass_l1=True)
    mk_run(tmp_path, "r-dev", "sympy-9", "r1", verdict="pass", pass_l1=True)
    out = api_cases(tmp_path, "r-dev", q="django", per_page=2, page=2)
    assert out["summary"]["PASS"] == 3      # sympy tersaring oleh q
    assert out["total"] == 3 and out["total_pages"] == 2
    assert len(out["cases"]) == 1


def test_api_cases_empty_campaign(tmp_path):
    from ui.server import api_cases
    out = api_cases(tmp_path, "r-dev")
    assert out["cases"] == [] and out["total"] == 0
    assert out["summary"] == {"PASS": 0, "FAIL": 0, "WAIT": 0,
                              "ANOMALY": 0, "?": 0}
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `python3 -m pytest tests/test_ui_api.py -q`
Expected: FAIL — `ImportError: cannot import name 'api_cases'`

- [ ] **Step 3: Implementasi** (setelah `api_runs`)

```python
def api_cases(root: Path, campaign: str, status: str | None = None,
              q: str | None = None, page: int = 1,
              per_page: int = PAGE_SIZE) -> dict:
    """Payload /api/cases: ringkasan per case "pernah qualified" (paritas
    panel ringkasan UI, via stage_summary). `summary` dihitung SETELAH
    filter q tapi SEBELUM filter status + paging (angka stabil).
    `latest_run` = run sumber status (run qualified bila PASS; run terbaru
    bila tidak)."""
    campaign_dir = Path(root) / campaign
    runs = filter_runs_by_case(list_runs(campaign_dir), q)
    s = stage_summary(campaign_dir, campaign, runs)
    run_count: dict[str, int] = {}
    for r in runs:
        rid = r.get("run_id")
        if isinstance(rid, str) and rid:
            cid, _ = split_run_id(rid)
            run_count[cid] = run_count.get(cid, 0) + 1
    cases = [{"case_id": i["case"], "status": i["status"],
              "category": i["category"], "reasons": i["reasons"],
              "latest_run": i["run_id"], "started": i["started"],
              "runs": run_count.get(i["case"], 0)}
             for i in s["items"]]
    if status is not None:
        cases = [c for c in cases if c["status"] == status]
    total = len(cases)
    page_items, total_pages = paginate(cases, page, per_page)
    return {"campaign": campaign,
            "summary": {"PASS": s["pass"], "FAIL": s["fail"],
                        "WAIT": s["wait"], "ANOMALY": s["anomaly"],
                        "?": s["unknown"]},
            "page": max(1, min(page, total_pages)),
            "total_pages": total_pages, "total": total,
            "cases": page_items}
```

- [ ] **Step 4: Jalankan test, pastikan pass**

Run: `python3 -m pytest tests/test_ui_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/server.py tests/test_ui_api.py
git commit -m "feat(ui): api_cases - ringkasan per-case JSON semantik pernah-qualified

Agent: claude-code"
```

---

### Task 5: Layer HTTP `/api/*` (routing + validasi + JSON response)

**Files:**
- Modify: `ui/server.py:1155-1201` (class Handler dalam `make_handler`)
- Test: `tests/test_ui_api.py`

**Interfaces:**
- Consumes: `api_campaigns`, `api_runs`, `api_cases`, `validate_name`, `_API_STATUSES`, `PAGE_SIZE`.
- Produces: route HTTP `GET /api/campaigns`, `GET /api/runs`, `GET /api/cases`; error `400/404` JSON `{"error": "..."}`.

- [ ] **Step 1: Tulis failing test** (append ke `tests/test_ui_api.py`)

```python
# --- HTTP layer /api/* ------------------------------------------------------

def _get_json(root, path):
    """Start server port-0, GET path, return (status_code, parsed_json)."""
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer

    from ui.server import make_handler
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    url = f"http://127.0.0.1:{srv.server_port}{path}"
    try:
        try:
            with urllib.request.urlopen(url) as resp:
                assert resp.headers["Content-Type"].startswith(
                    "application/json")
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = json.loads(e.read().decode("utf-8"))
            return e.code, body
    finally:
        srv.shutdown()
        srv.server_close()


def test_http_api_campaigns(tmp_path):
    code, body = _get_json(tmp_path, "/api/campaigns")
    assert code == 200
    assert [c["name"] for c in body["campaigns"]] == \
        ["r-dev", "l-dev", "f-dev"]


def test_http_api_runs_full_roundtrip(tmp_path):
    mk_run(tmp_path, "r-dev", "django__django-1", "r1",
           verdict="pass", pass_l1=True)
    mk_run(tmp_path, "r-dev", "sympy__sympy-2", "r1", verdict="wrong-logic")
    code, body = _get_json(
        tmp_path, "/api/runs?c=r-dev&status=FAIL&q=sympy&page=1&per_page=5")
    assert code == 200
    assert body["total"] == 1
    assert body["runs"][0]["case"] == "sympy__sympy-2"


def test_http_api_cases_roundtrip(tmp_path):
    mk_run(tmp_path, "r-dev", "case-A", "r1", verdict="pass", pass_l1=True)
    code, body = _get_json(tmp_path, "/api/cases?c=r-dev")
    assert code == 200 and body["summary"]["PASS"] == 1


def test_http_api_missing_c_is_400(tmp_path):
    code, body = _get_json(tmp_path, "/api/runs")
    assert code == 400 and "error" in body


def test_http_api_bad_campaign_name_is_400(tmp_path):
    code, body = _get_json(tmp_path, "/api/runs?c=../etc")
    assert code == 400 and "error" in body


def test_http_api_bad_status_is_400(tmp_path):
    code, body = _get_json(tmp_path, "/api/runs?c=r-dev&status=MAYBE")
    assert code == 400 and "error" in body


def test_http_api_unknown_path_is_404_json(tmp_path):
    code, body = _get_json(tmp_path, "/api/tidak-ada")
    assert code == 404 and "error" in body


def test_http_api_bad_page_falls_back(tmp_path):
    mk_run(tmp_path, "r-dev", "case-A", "r1", verdict="pass", pass_l1=True)
    code, body = _get_json(tmp_path, "/api/runs?c=r-dev&page=xx&per_page=yy")
    assert code == 200 and body["page"] == 1
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `python3 -m pytest tests/test_ui_api.py -q`
Expected: test `test_http_api_*` FAIL (path `/api/...` sekarang jatuh ke 404 HTML → `Content-Type` assertion / JSONDecodeError).

- [ ] **Step 3: Implementasi**

Di class `Handler` (`ui/server.py`), tambah setelah `_send_html`:

```python
        def _send_json(self, obj, status: int = 200) -> None:
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type",
                             "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _api(self, path: str, qs: dict) -> None:
            """Routing /api/* (kontrak: docs/api-ui-viewer.md)."""
            if path == "/api/campaigns":
                self._send_json(api_campaigns(root))
                return
            if path not in ("/api/runs", "/api/cases"):
                self._send_json({"error": "tidak ditemukan"}, 404)
                return
            camp = (qs.get("c") or [""])[0]
            if not validate_name(camp):
                self._send_json(
                    {"error": "parameter c wajib berupa nama campaign "
                              "yang sah"}, 400)
                return
            status = (qs.get("status") or [None])[0]
            if status is not None and status not in _API_STATUSES:
                self._send_json(
                    {"error": "status harus salah satu dari: "
                              + ", ".join(_API_STATUSES)}, 400)
                return
            q = (qs.get("q") or [None])[0]
            if q is not None:
                q = q[:100]
            try:
                page = int((qs.get("page") or ["1"])[0])
            except ValueError:
                page = 1
            try:
                per_page = int((qs.get("per_page")
                                or [str(PAGE_SIZE)])[0])
            except ValueError:
                per_page = PAGE_SIZE
            per_page = max(1, min(per_page, 100))
            fn = api_runs if path == "/api/runs" else api_cases
            self._send_json(fn(root, camp, status=status, q=q,
                               page=page, per_page=per_page))
```

Di `do_GET`, tambah cabang SEBELUM `else` 404 (setelah blok `/run`):

```python
            elif parsed.path.startswith("/api/"):
                self._api(parsed.path, qs)
```

- [ ] **Step 4: Jalankan seluruh suite**

Run: `python3 -m pytest tests/ -q`
Expected: semua PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/server.py tests/test_ui_api.py
git commit -m "feat(ui): route /api/campaigns /api/runs /api/cases - JSON read-only

Agent: claude-code"
```

---

### Task 6: Dokumentasi API + pointer

**Files:**
- Create: `docs/api-ui-viewer.md`
- Modify: `ui/server.py:1-8` (docstring), `README.md` (bila ada seksi UI)

**Interfaces:**
- Consumes: perilaku final Task 2-5.
- Produces: referensi lengkap untuk agent sesi lain — cukup baca file ini untuk memakai API.

- [ ] **Step 1: Tulis `docs/api-ui-viewer.md`**

```markdown
# API JSON — UI Log Viewer

Referensi untuk AGENT (atau klien programatik lain) membaca data harness
SWE-bench tanpa parse HTML. Server: `ui/server.py` (stdlib only, read-only).

- Base URL default: `http://127.0.0.1:8766` (`python ui/server.py`,
  opsi `--root/--port/--host`).
- Semua endpoint `GET`, respons `application/json; charset=utf-8`.
- Read-only: tidak ada endpoint tulis.
- Sumber data: direktori `artifacts/` (kontrak: `docs/kontrak-output.md`).
- Semantik status DIJAMIN paritas dengan UI HTML — dihitung lewat jalur
  logika yang sama (`case_status`, `stage_summary`).

## Enum status

| Status | Arti |
|---|---|
| `PASS` | qualified (r-dev: verdict pass + flip terkonfirmasi; l-*: L1 pass + gold_eval qualified; f-*: pass_l1 DAN swebench resolved) |
| `FAIL` | tidak qualified (kategori + alasan di field `category`/`reasons`) |
| `WAIT` | f-* product-pass menunggu VERIFY (swebench_eval.json belum ada) |
| `ANOMALY` | f-* kontradiksi sinyal: product FAIL tapi SWE-bench resolved |
| `?` | verdict.json tidak ada / rusak |

## GET /api/campaigns

Daftar kampanye/stage urut pipeline (stage pipeline selalu tampil walau
belum punya run — paritas tab UI).

    curl -s http://127.0.0.1:8766/api/campaigns

    {"campaigns": [
      {"name": "r-dev", "label": "REPRODUCE", "phase": "R"},
      {"name": "l-dev", "label": "LOCALIZE", "phase": "L"},
      {"name": "f-dev", "label": "FIX and VERIFY", "phase": "FV"}]}

## GET /api/runs

Run individual sebuah kampanye, urut mulai (started) descending.

| Param | Wajib | Default | Arti |
|---|---|---|---|
| `c` | ya | — | nama kampanye (`r-dev`/`l-dev`/`f-dev`/...) |
| `status` | tidak | semua | filter `PASS`/`FAIL`/`WAIT`/`ANOMALY`/`?` — `?` di-URL-encode jadi `%3F` |
| `q` | tidak | semua | substring nama case, case-insensitive (maks 100 char) |
| `page` | tidak | 1 | 1-based, di-clamp ke rentang sah |
| `per_page` | tidak | 15 | 1..100 |

    curl -s 'http://127.0.0.1:8766/api/runs?c=r-dev&status=FAIL&q=django&page=1'

    {"campaign": "r-dev", "page": 1, "total_pages": 1, "total": 2,
     "runs": [
       {"run_id": "r-dev--django__django-11583--r2",
        "case": "django__django-11583", "rerun": "r2",
        "verdict": "wrong-logic", "status": "FAIL",
        "category": "wrong-logic",
        "reasons": ["..."], "wall": 123.4,
        "started": "2026-07-21 14:03"}]}

Catatan field:

- `verdict` = teks gabungan kolom verdict UI (verdict L1 + merge
  `gold_eval.json`; mis. `pass`, `wrong-file`, `pass (no-eval)`), BUKAN
  verdict.json mentah.
- `status`/`category`/`reasons` = `case_status()` run itu (di f-* sudah
  2-lapisan L1+L2).
- `wall` dari runs.jsonl event `end`; run hidup/legacy → `null`.
- `total` = jumlah run SETELAH filter `status`+`q`, sebelum paging.
- Kampanye sah tapi tak dikenal → 200 dengan `runs: []` (bukan 404).

## GET /api/cases

Ringkasan per case, semantik "pernah qualified": case `PASS` bila ≥1
run-nya qualified; selain itu status+kategori+alasan dari run TERBARU.
Parameter sama dengan `/api/runs`.

    curl -s 'http://127.0.0.1:8766/api/cases?c=r-dev&status=FAIL'

    {"campaign": "r-dev",
     "summary": {"PASS": 12, "FAIL": 5, "WAIT": 0, "ANOMALY": 0, "?": 1},
     "page": 1, "total_pages": 1, "total": 5,
     "cases": [
       {"case_id": "django__django-11583", "status": "FAIL",
        "category": "wrong-logic", "reasons": ["..."],
        "latest_run": "r-dev--django__django-11583--r3",
        "started": "2026-07-21 14:03", "runs": 3}]}

Catatan field:

- `summary` dihitung SETELAH filter `q` tapi SEBELUM filter `status` dan
  paging — stabil saat pindah halaman/filter status.
- `latest_run` = run sumber status (run qualified bila PASS; run terbaru
  bila tidak).
- `runs` = jumlah run case itu (setelah filter `q`).

## Error

- `400 {"error": "..."}` — `c` absen/tidak sah, atau `status` di luar enum.
- `404 {"error": "tidak ditemukan"}` — path `/api/*` lain.
- `page`/`per_page` bukan angka → fallback default (bukan error).

## Resep umum untuk agent

    # kampanye apa saja yang ada?
    curl -s $BASE/api/campaigns
    # case mana yang belum pernah pass di REPRODUCE?
    curl -s "$BASE/api/cases?c=r-dev&status=FAIL"
    # kenapa run terakhir case 11583 gagal?
    curl -s "$BASE/api/runs?c=r-dev&q=11583" | head
    # autopsi mendalam: baca langsung artifacts/<campaign>/<run_id>/
    # (events.jsonl, console.log, verdict.json) — tidak lewat API.
```

- [ ] **Step 2: Tambah pointer di docstring `ui/server.py`**

Ubah docstring (line 1-8) menjadi:

```python
"""UI log viewer sederhana untuk artifacts harness SWE-bench.

Stdlib only (Python 3.12). Baca-saja: tidak pernah menulis ke artifacts.
Kontrak data: docs/kontrak-output.md (schema_version 1.0.0).
API JSON untuk agent: /api/campaigns /api/runs /api/cases —
kontrak lengkap di docs/api-ui-viewer.md.

Jalankan:
    python ui\\server.py [--root <artifacts_dir>] [--port 8766]
"""
```

- [ ] **Step 3: Cek README**

Run: `grep -n "ui/server\|log viewer" README.md`
Bila ada seksi UI viewer, tambah satu kalimat: `API JSON untuk agent: lihat docs/api-ui-viewer.md.` Bila tidak ada, lewati.

- [ ] **Step 4: Verifikasi contoh dokumen jujur**

Jalankan server terhadap artifacts sungguhan dan cocokkan bentuk respons dengan contoh dokumen (field & tipe — nilai boleh beda):

```bash
python3 ui/server.py --port 8799 &
sleep 1
curl -s http://127.0.0.1:8799/api/campaigns
curl -s 'http://127.0.0.1:8799/api/runs?c=r-dev&per_page=2'
curl -s 'http://127.0.0.1:8799/api/cases?c=r-dev&per_page=2'
kill %1
```

Expected: JSON valid, field sesuai dokumen.

- [ ] **Step 5: Commit**

```bash
git add docs/api-ui-viewer.md ui/server.py README.md
git commit -m "docs(api): referensi API JSON UI viewer utk agent lintas sesi

Agent: claude-code"
```

---

### Task 7: Verifikasi akhir

- [ ] **Step 1: Seluruh test suite**

Run: `python3 -m pytest tests/ -q`
Expected: semua PASS, 0 failed.

- [ ] **Step 2: Smoke end-to-end dua wajah (HTML + JSON)**

```bash
python3 ui/server.py --port 8799 &
sleep 1
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8799/          # 200 HTML
curl -s 'http://127.0.0.1:8799/api/cases?c=r-dev' | python3 -m json.tool | head -20
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8799/api/runs' # 400
kill %1
```

Expected: 200 / JSON rapi / 400.

- [ ] **Step 3: Push**

```bash
git push
```
