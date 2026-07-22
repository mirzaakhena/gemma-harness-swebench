# Filter Status Server-Side + Klik-Case — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Filter All/PASS/FAIL dashboard jadi server-side (berlaku ke seluruh data + paging ikut filter, dibawa lintas tab), klik nama case mengisi filter `q`, plus bundle minor final review API JSON.

**Architecture:** `page_index` direfaktor dua-pass (status baris dihitung untuk semua run terfilter `q` → filter `status` → paginasi → field mahal hanya untuk halaman aktif). Radio jadi GET form auto-submit; `status` dibawa di link tab/pager/search seperti `q`.

**Tech Stack:** Python 3.12 stdlib only, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-ui-filter-server-side-design.md`

## Global Constraints

- Stdlib only (Python 3.12) — TANPA dependensi baru.
- Read-only mutlak: viewer tidak pernah menulis ke `artifacts/`.
- Kerja di `/Users/mirza/Workspace/gemma-harness-swebench/main`, branch `main`.
- Test dari `main/`: `python3 -m pytest tests/ -q`.
- SETIAP commit wajib trailer `Agent: claude-code`.
- Gaya kode ui/server.py: komentar Indonesia, fail-soft, baris BARU ≤ 79 char.
- Perilaku tanpa param `status` identik dengan sekarang (test page_index lama = jaring regresi).
- Param `status` UI hanya `PASS`|`FAIL`; nilai lain → dianggap All (fail-soft, tanpa error).

---

### Task 1: Bundle minor final review (paginate guard + spec wording + test %3F)

**Files:**
- Modify: `ui/server.py` (fungsi `paginate`, ~line 250)
- Modify: `docs/superpowers/specs/2026-07-22-ui-json-api-design.md` (baris "summary dihitung SEBELUM")
- Test: `tests/test_ui_api.py` (append), `tests/test_ui_core.py` TIDAK diubah

**Interfaces:**
- Consumes: `paginate(items, page, per_page=15)`, fixture `mk_run`, helper `_get_json` (sudah ada di test_ui_api.py).
- Produces: `paginate` kebal `per_page <= 0` (diperlakukan sbg 1). Tidak ada perubahan signature.

- [ ] **Step 1: Tulis failing test** (append ke `tests/test_ui_api.py`)

```python
# --- bundle minor final review ---------------------------------------------

def test_paginate_per_page_zero_is_safe():
    from ui.server import paginate
    items = list(range(3))
    page_items, total = paginate(items, 1, per_page=0)
    assert page_items == [0] and total == 3   # per_page<=0 -> 1


def test_http_api_status_unknown_enum_url_encoded(tmp_path):
    # status "?" ter-URL-encode (%3F) harus lolos enum dan menyaring
    # hanya run tanpa verdict.json
    mk_run(tmp_path, "r-dev", "case-live", "r1")  # tanpa verdict -> "?"
    mk_run(tmp_path, "r-dev", "case-ok", "r1",
           verdict="pass", pass_l1=True)
    code, body = _get_json(tmp_path, "/api/runs?c=r-dev&status=%3F")
    assert code == 200 and body["total"] == 1
    assert body["runs"][0]["case"] == "case-live"
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `python3 -m pytest tests/test_ui_api.py -q`
Expected: `test_paginate_per_page_zero_is_safe` FAIL dengan `ZeroDivisionError`; test %3F kemungkinan PASS (fitur sudah ada — test mengunci kontrak; itu bukan masalah).

- [ ] **Step 3: Implementasi guard**

Di `ui/server.py`, fungsi `paginate`, tambahkan baris pertama fungsi:

```python
def paginate(items: list, page: int, per_page: int = 15) -> tuple[list, int]:
    """(potongan halaman, total_halaman); page 1-based, di-clamp."""
    per_page = max(1, per_page)   # pemanggil langsung bisa kirim 0/negatif
    total = max(1, -(-len(items) // per_page))
    page = max(1, min(page, total))
    start = (page - 1) * per_page
    return items[start:start + per_page], total
```

- [ ] **Step 4: Presisi wording spec API §3**

Di `docs/superpowers/specs/2026-07-22-ui-json-api-design.md`, ganti baris:

```
- `summary` dihitung SEBELUM filter/paging supaya angka total stabil.
```

menjadi:

```
- `summary` dihitung SETELAH filter `q`, SEBELUM filter `status` dan
  paging — angka stabil saat pindah halaman/filter status.
```

- [ ] **Step 5: Jalankan seluruh suite**

Run: `python3 -m pytest tests/ -q`
Expected: semua PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/server.py tests/test_ui_api.py docs/superpowers/specs/2026-07-22-ui-json-api-design.md
git commit -m "fix(ui): bundle minor final review - guard per_page, test status=%3F, presisi spec summary

Agent: claude-code"
```

---

### Task 2: Filter status server-side di page_index

**Files:**
- Modify: `ui/server.py` — `_search_box` (~line 962), `_row_status_from_icon` (tetap), `page_index` (~line 1005-1133), `_MODAL_JS` (hapus `filterRows`), handler `do_GET` route `/` (~line 1290)
- Test: `tests/test_ui_api.py` (append; fixture `mk_run` dipakai ulang)

**Interfaces:**
- Consumes: `run_index_verdict`, `case_status`, `status_icon`, `run_liveness`, `_row_status_from_icon`, `paginate`, `PAGE_SIZE`, `mk_run`.
- Produces: `page_index(root, tab=None, page=1, q=None, status=None)` — `status` `"PASS"`/`"FAIL"`/None; `_search_box(active, q, status=None)`; helper baru `_status_filter_form(active, q, status)`.

- [ ] **Step 1: Tulis failing tests** (append ke `tests/test_ui_api.py`)

```python
# --- filter status server-side page_index (permintaan Mirza 2026-07-22) ----

def test_page_index_status_filter_across_pages(tmp_path):
    from ui.server import page_index
    # 16 FAIL + 5 PASS: tanpa filter 21 run; dengan status=FAIL paging
    # dihitung dari set terfilter (16 -> 2 halaman) dan PASS tak tampil
    for i in range(16):
        mk_run(tmp_path, "r-dev", f"failcase-{i:02d}", "r1",
               verdict="wrong-logic",
               started=f"2026-07-01T10:{i:02d}:00+07:00")
    for i in range(5):
        mk_run(tmp_path, "r-dev", f"okcase-{i}", "r1", verdict="pass",
               pass_l1=True, started=f"2026-07-02T10:0{i}:00+07:00")
    out = page_index(tmp_path, tab="r-dev", page=1, status="FAIL")
    assert "okcase-" not in out
    assert "16 run cocok" in out
    assert "hal 1/2" in out               # paging ikut set terfilter
    page2 = page_index(tmp_path, tab="r-dev", page=2, status="FAIL")
    assert "failcase-" in page2 and "okcase-" not in page2


def test_page_index_status_carried_in_links(tmp_path):
    from ui.server import page_index
    for i in range(16):
        mk_run(tmp_path, "r-dev", f"failcase-{i:02d}", "r1",
               verdict="wrong-logic",
               started=f"2026-07-01T10:{i:02d}:00+07:00")
    out = page_index(tmp_path, tab="r-dev", page=1, status="FAIL")
    # link tab lain membawa status (filter global lintas stage)
    assert "/?tab=l-dev&status=FAIL" in out
    # pager membawa status
    assert "status=FAIL&page=2" in out
    # radio tercentang sesuai param
    assert "value='FAIL' checked" in out


def test_page_index_status_empty_result_safe(tmp_path):
    from ui.server import page_index
    mk_run(tmp_path, "r-dev", "case-ok", "r1", verdict="pass",
           pass_l1=True)
    out = page_index(tmp_path, tab="r-dev", status="FAIL")
    assert "tidak ada run dengan status ini" in out


def test_page_index_no_status_regression(tmp_path):
    from ui.server import page_index
    mk_run(tmp_path, "r-dev", "case-ok", "r1", verdict="pass",
           pass_l1=True)
    mk_run(tmp_path, "r-dev", "case-bad", "r1", verdict="wrong-logic")
    out = page_index(tmp_path, tab="r-dev")
    assert "case-ok" in out and "case-bad" in out
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `python3 -m pytest tests/test_ui_api.py -q`
Expected: FAIL — `page_index() got an unexpected keyword argument 'status'`.

- [ ] **Step 3: Implementasi**

3a. Ganti `_search_box` menjadi (signature + hidden status + clear link membawa status):

```python
def _search_box(active: str, q: str | None,
                status: str | None = None) -> str:
    """Kotak search/filter by nama case (GET form). `tab` (+`status` bila
    aktif) dibawa sbg hidden field supaya submit tetap di tab & filter
    status aktif; q terisi ulang. Tautan 'hapus' muncul saat filter aktif."""
    qval = html.escape(q or "", quote=True)
    ssuffix = ("&status=" + urllib.parse.quote(status)) if status else ""
    clear = ("<a class='clear' href='/?tab=" + urllib.parse.quote(active)
             + ssuffix + "'>&times; hapus filter</a>") if q else ""
    hidden_status = (f"<input type='hidden' name='status' "
                     f"value='{html.escape(status, quote=True)}'>"
                     if status else "")
    return ("<form class='search' method='get' action='/'>"
            f"<input type='hidden' name='tab' value='{html.escape(active, quote=True)}'>"
            + hidden_status +
            f"<input type='text' name='q' value='{qval}' "
            "placeholder='cari nama case (mis. 15902 atau django-114)' "
            "autocomplete='off'>"
            "<button type='submit'>cari</button>"
            + clear + "</form>")
```

3b. Tambah helper baru setelah `_search_box`:

```python
def _status_filter_form(active: str, q: str | None,
                        status: str | None) -> str:
    """Radio filter status server-side All/PASS/FAIL (permintaan Mirza
    2026-07-22) — GET form auto-submit; tab & q dibawa hidden. Nilai
    'All' dikirim apa adanya dan dinormalkan jadi None di handler."""
    opts = []
    for val in ("All", "PASS", "FAIL"):
        sel = " checked" if (status or "All") == val else ""
        opts.append(
            f"<label><input type='radio' name='status' value='{val}'"
            f"{sel} onchange='this.form.submit()'> {val}</label>")
    hidden = [f"<input type='hidden' name='tab' "
              f"value='{html.escape(active, quote=True)}'>"]
    if q:
        hidden.append(f"<input type='hidden' name='q' "
                      f"value='{html.escape(q, quote=True)}'>")
    return ("<form class='rfilter' method='get' action='/'>filter: "
            + "".join(hidden) + "".join(opts) + "</form>")
```

3c. Refaktor `page_index`. Signature:

```python
def page_index(root: Path, tab: str | None = None, page: int = 1,
               q: str | None = None, status: str | None = None) -> str:
```

Setelah baris `qsuffix = ...` tambahkan:

```python
    # status dibawa lintas tab & halaman — paritas perilaku q
    # (permintaan Mirza 2026-07-22: filter global utk ketiga stage)
    ssuffix = ("&status=" + urllib.parse.quote(status)) if status else ""
```

Link tab: ganti href jadi `/?tab={camp}{qsuffix}{ssuffix}`:

```python
        tab_links.append(
            f"<a{cls} href='/?tab={urllib.parse.quote(camp)}{qsuffix}"
            f"{ssuffix}'>"
            f"{html.escape(campaign_label(camp))}</a>")
```

Panggilan search box: `parts.append(_search_box(active, q, status))`.

Blok radio lama (parts.append dengan `rowfilter`/`filterRows`) DIGANTI:

```python
    # radio filter status — server-side, berlaku ke seluruh data
    # (permintaan Mirza 2026-07-22; dulu client-side filterRows)
    parts.append(_status_filter_form(active, q, status))
```

Blok mulai `page_runs, total_pages = paginate(runs, page, PAGE_SIZE)` sampai akhir loop baris DIGANTI dua-pass:

```python
    # pass 1: hitung status baris SEMUA run terfilter q — filter status
    # harus berlaku lintas seluruh data SEBELUM paginasi; field mahal
    # (durasi/turns) ditunda ke pass 2 (halaman aktif saja)
    row_meta = []
    for r in runs:
        rid = r["run_id"]
        run_dir = root / active / rid
        vpath = run_dir / "verdict.json"
        vtext, icon = run_index_verdict(active, run_dir)
        if vpath.is_file() and active.startswith("f-"):
            # ikon baris disinkronkan ke status 2-lapisan (spec §6)
            # — teks verdict TETAP vonis L1 produk apa adanya
            # (permintaan Mirza: viewer verify-fail jangan lagi ✅).
            two_status = case_status(active, run_dir)
            icon = status_icon(two_status["status"])
        has_verdict = vpath.is_file()
        if not has_verdict and run_liveness(run_dir) == "stale":
            # marker STALE (dibunuh/ditinggalkan) — beda dari run live
            # (ikon kosong) & dari pass/fail (permintaan Mirza 2026-07-22)
            icon = "➖ "
        row_meta.append({"rid": rid, "vtext": vtext, "icon": icon,
                         "has_verdict": has_verdict,
                         "status": _row_status_from_icon(icon)})

    if status:
        row_meta = [m for m in row_meta if m["status"] == status]
        parts.append(f"<p class='dim'>filter status: "
                     f"<b>{html.escape(status)}</b> &middot; "
                     f"{len(row_meta)} run cocok</p>")
        if not row_meta:
            parts.append("<p class='dim'>(tidak ada run dengan status "
                         "ini)</p>")
            return _page("log viewer", "".join(parts))

    page_meta, total_pages = paginate(row_meta, page, PAGE_SIZE)
    rows = []
    for m in page_meta:
        rid = m["rid"]
        run_dir = root / active / rid
        vtext, icon = m["vtext"], m["icon"]
        href = ("/run?c=" + urllib.parse.quote(active)
                + "&r=" + urllib.parse.quote(rid))
        dur = fmt_duration(run_duration_seconds(run_dir))
        if not m["has_verdict"]:
            # run tanpa verdict.json: label live/stale (ikon di pass 1)
            dur += _live_label(run_dir)
        turns = run_turns(run_dir)
        case_id, rerun = split_run_id(rid)
        row_status = m["status"]
        if row_status in ("FAIL", "ANOMALY"):
            item = reason_by_case.get(case_id)
            rtext = (_fail_reason_text(item) if item
                     else "(detail tidak terekam)")
            icon_cell = (
                "<button type='button' class='xbtn' "
                f"data-case=\"{html.escape(case_id, quote=True)}\" "
                f"data-reason=\"{html.escape(rtext, quote=True)}\" "
                f"onclick='showReason(this)'>{icon}</button>")
        else:
            icon_cell = icon
        # tombol copy-to-clipboard di sebelah nama case: menyalin string
        # JSON {"case": ..., "phase": ..., "run": ...} — phase dari
        # kampanye aktif, run = rerun baris ini (split_run_id di atas).
        copy_json = copy_case_json(case_id, active, rerun)
        copy_btn = (
            "<button type='button' class='copybtn' title='copy JSON' "
            f"data-copy=\"{html.escape(copy_json, quote=True)}\" "
            "onclick='copyCaseJSON(this)'>📋</button>")
        rows.append(
            f"<tr data-status=\"{html.escape(row_status, quote=True)}\">"
            f"<td>{html.escape(case_id)} {copy_btn}</td>"
            f"<td><a href='{href}'>{html.escape(rerun or rid)}</a></td>"
            f"<td>{icon_cell}</td>"
            f"<td>{html.escape(vtext)}</td>"
            f"<td class='dim'>{html.escape(dur)}</td>"
            f"<td class='dim'>{turns if turns is not None else '-'}</td>"
            f"<td class='dim'>"
            f"{html.escape(run_started_str(run_dir))}</td></tr>")
```

CATATAN: `<td>` nama case masih TANPA link — link menyusul di Task 3.

Pager: ganti baris `base = ...` menjadi:

```python
        base = ("/?tab=" + urllib.parse.quote(active) + qsuffix + ssuffix
                + "&page=")
```

3d. Hapus fungsi `filterRows` dari `_MODAL_JS` (blok `function filterRows(v){...}` utuh). Atribut `data-status` baris DIPERTAHANKAN (dipakai test).

3e. Handler `do_GET` route `/`: setelah parsing `q`, tambah:

```python
                status = (qs.get("status") or [None])[0]
                if status not in ("PASS", "FAIL"):
                    status = None   # "All"/nilai lain -> tanpa filter
                self._send_html(page_index(root, tab=tab, page=page, q=q,
                                           status=status))
```

(mengganti pemanggilan `page_index` lama.)

- [ ] **Step 4: Jalankan seluruh suite**

Run: `python3 -m pytest tests/ -q`
Expected: semua PASS — termasuk test page_index lama (regresi perilaku tanpa status).

- [ ] **Step 5: Commit**

```bash
git add ui/server.py tests/test_ui_api.py
git commit -m "feat(ui): filter status All/PASS/FAIL server-side + global lintas tab

Agent: claude-code"
```

---

### Task 3: Klik nama case → filter q

**Files:**
- Modify: `ui/server.py` (loop baris `page_index`, sel `<td>` pertama)
- Test: `tests/test_ui_api.py` (append)

**Interfaces:**
- Consumes: `ssuffix` (Task 2, sudah dalam scope `page_index`), `mk_run`.
- Produces: nama case dirender sebagai `<a href='/?tab=<aktif>&q=<case_id><ssuffix>'>`.

- [ ] **Step 1: Tulis failing test** (append ke `tests/test_ui_api.py`)

```python
def test_page_index_case_name_links_to_q_filter(tmp_path):
    from ui.server import page_index
    mk_run(tmp_path, "r-dev", "django__django-1", "r1",
           verdict="pass", pass_l1=True)
    out = page_index(tmp_path, tab="r-dev")
    assert "href='/?tab=r-dev&q=django__django-1'" in out


def test_page_index_case_link_carries_status(tmp_path):
    from ui.server import page_index
    mk_run(tmp_path, "r-dev", "case-bad", "r1", verdict="wrong-logic")
    out = page_index(tmp_path, tab="r-dev", status="FAIL")
    assert "href='/?tab=r-dev&q=case-bad&status=FAIL'" in out
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `python3 -m pytest tests/test_ui_api.py -q`
Expected: kedua test baru FAIL (belum ada link case).

- [ ] **Step 3: Implementasi**

Di loop pass 2 `page_index`, setelah `case_id, rerun = split_run_id(rid)` tambah:

```python
        # klik nama case -> auto-isi filter "cari nama case" (permintaan
        # Mirza 2026-07-22); status aktif ikut dibawa
        case_href = ("/?tab=" + urllib.parse.quote(active)
                     + "&q=" + urllib.parse.quote(case_id) + ssuffix)
```

dan ganti sel pertama baris tabel:

```python
            f"<td><a href='{case_href}'>{html.escape(case_id)}</a> "
            f"{copy_btn}</td>"
```

- [ ] **Step 4: Jalankan seluruh suite**

Run: `python3 -m pytest tests/ -q`
Expected: semua PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/server.py tests/test_ui_api.py
git commit -m "feat(ui): klik nama case -> auto filter cari nama case

Agent: claude-code"
```

---

### Task 4: Verifikasi akhir

- [ ] **Step 1:** `python3 -m pytest tests/ -q` → semua PASS.
- [ ] **Step 2:** Smoke nyata: jalankan server port 8799, cek `/?tab=r-dev&status=FAIL` (baris ❌ semua + pager membawa status), klik-link case ada, `/?status=All` = tanpa filter; matikan server.
- [ ] **Step 3:** `git push`.
