# Desain: API JSON untuk UI Log Viewer

Tanggal: 2026-07-22
Status: disetujui Mirza (brainstorming sesi 2026-07-22)

## Tujuan

Agent (Claude atau lainnya) perlu membaca data harness secara programatik dan
hemat token, sementara manusia tetap memakai UI HTML di browser. Saat ini
`ui/server.py` hanya menyajikan HTML (`/` dan `/run`), sehingga agent harus
parse HTML atau membaca file artifacts langsung.

Kebutuhan dari Mirza:

- Agent bisa melihat semua informasi per stage pipeline: REPRODUCE (`r-dev`),
  LOCALIZE (`l-dev`), FIX and VERIFY (`f-dev`).
- Filter berdasarkan status PASS/FAIL, paging, dan filter nama case.
- Filter berlaku di DUA unit: daftar RUN individual dan ringkasan per CASE.
- TIDAK perlu endpoint detail satu run (agent baca file artifacts langsung
  bila perlu autopsi mendalam).
- Dokumentasi API tersendiri supaya agent lain di sesi berbeda bisa langsung
  pakai tanpa membaca kode.

## Pendekatan terpilih

Route `/api/*` ditambahkan di server yang sama (`ui/server.py`), memakai ulang
fungsi inti yang sudah ada (`list_runs`, `case_status`, `stage_summary`,
`filter_runs_by_case`, `paginate`, `split_run_id`, `run_started_str`).

Alasan: satu proses satu port (manusia buka `/`, agent curl `/api/...`), data
dijamin konsisten dengan UI karena melewati jalur logika yang sama, dan
batasan "stdlib only, read-only" tetap terjaga.

Alternatif yang ditolak:

- Content negotiation (`?format=json` di route HTML): mencampur concern render
  dengan serialisasi; bentuk respons terikat bentuk halaman.
- Server API terpisah: dua proses, duplikasi startup/arg parsing — overkill
  untuk viewer read-only.

## Endpoint

Semua endpoint GET, read-only, `Content-Type: application/json; charset=utf-8`.

### 1. `GET /api/campaigns`

Discovery daftar kampanye/stage, paritas dengan tab UI (stage pipeline tampil
walau direktorinya belum ada).

```json
{"campaigns": [
  {"name": "r-dev", "label": "REPRODUCE", "phase": "R"},
  {"name": "l-dev", "label": "LOCALIZE", "phase": "L"},
  {"name": "f-dev", "label": "FIX and VERIFY", "phase": "FV"}
]}
```

Urutan = urutan pipeline (`order_campaigns` + `with_stage_tabs`); kampanye di
luar pipeline menyusul terurut nama dengan `label` = nama apa adanya.

### 2. `GET /api/runs`

Daftar run individual sebuah kampanye.

Parameter query:

| Param | Wajib | Default | Arti |
|---|---|---|---|
| `c` | ya | — | nama kampanye (divalidasi `validate_name`) |
| `status` | tidak | (semua) | `PASS`/`FAIL`/`WAIT`/`ANOMALY`/`?` — hasil `case_status()` per run |
| `q` | tidak | (semua) | substring case-insensitive nama case (logika = kotak search UI, dipangkas 100 char) |
| `page` | tidak | 1 | 1-based, di-clamp |
| `per_page` | tidak | 15 | maks 100 |

Respons:

```json
{"campaign": "r-dev", "page": 1, "total_pages": 7, "total": 98,
 "runs": [
   {"run_id": "r-dev--django__django-11583--r2",
    "case": "django__django-11583", "rerun": "r2",
    "verdict": "pass", "status": "PASS", "category": "pass",
    "reasons": [], "wall": 123.4, "started": "2026-07-21 14:03"}
 ]}
```

Semantik:

- `status`/`category`/`reasons` = hasil `case_status()` pada run itu — sudah
  termasuk merge `gold_eval.json` dan status 2-lapisan kampanye `f-*`
  (konsisten dengan ikon di tabel UI).
- `verdict` = verdict gabungan yang tampil di kolom tabel UI (hasil
  `index_row_verdict` + `merge_gold_verdict`), bukan verdict.json mentah.
- Urutan = started desc (sama dengan UI, `sort_runs_desc`).
- `total` = jumlah run SETELAH filter (`status` dan `q`), sebelum paging.
- Kampanye valid tapi tak punya direktori/run → 200 dengan `runs: []`.

### 3. `GET /api/cases`

Ringkasan per case dengan semantik "pernah qualified" (persis panel ringkasan
UI): case PASS bila ≥1 run-nya qualified; selain itu status + kategori +
alasan diambil dari run TERBARU case itu.

Parameter sama dengan `/api/runs` (`c`, `status`, `q`, `page`, `per_page`).

```json
{"campaign": "r-dev",
 "summary": {"PASS": 12, "FAIL": 5, "WAIT": 0, "ANOMALY": 0, "?": 1},
 "page": 1, "total_pages": 2, "total": 18,
 "cases": [
   {"case_id": "django__django-11583", "status": "FAIL",
    "category": "wrong-logic", "reasons": ["..."],
    "latest_run": "r-dev--django__django-11583--r3", "runs": 3}
 ]}
```

Semantik:

- `summary` dihitung SEBELUM filter/paging supaya angka total stabil.
- `total`/paging berlaku pada daftar cases setelah filter.
- `runs` = jumlah run case itu.

## Penanganan error

- Parameter `c` absen/tidak lolos `validate_name`, atau `status` di luar enum
  → `400 {"error": "<pesan>"}`.
- `page`/`per_page` bukan angka → fallback default (konsisten fail-soft UI).
- Path `/api/*` lain → `404 {"error": "tidak ditemukan"}`.
- Kampanye tak dikenal (lolos validasi nama tapi tak ada direktorinya) →
  200 daftar kosong, BUKAN 404 (konsisten fail-soft UI).

## Dokumentasi API

File baru `docs/api-ui-viewer.md`: referensi lengkap endpoint di atas —
base URL default (`http://127.0.0.1:8766`), tabel parameter, contoh `curl` +
respons, enum status dan artinya, dan catatan semantik (pernah-qualified,
summary sebelum filter). Ditulis untuk pembaca agent di sesi lain: cukup baca
file itu untuk memakai API tanpa membuka `server.py`.

`ui/server.py` docstring dan `README.md` (bila menyinggung UI) diberi pointer
ke dokumen ini.

## Testing

Unit test di `tests/test_ui_core.py` mengikuti pola tes yang sudah ada
(artifacts sintetis di tmp_path):

- Serialisasi baris run (`status`, `verdict`, `case`, `rerun`, `started`).
- Filter `status` di runs dan cases (termasuk enum tak sah → 400 di layer
  handler).
- Filter `q` + paging (clamp, per_page maks 100).
- `summary` tak terpengaruh filter.
- Artifacts kosong / verdict.json rusak → fail-soft (status `?`), tidak crash.
- Handler: `Content-Type` JSON, 400 untuk `c` tidak sah, 404 JSON untuk
  `/api/x`.

## Batasan

- Read-only mutlak: tidak ada endpoint tulis, viewer tidak pernah menulis ke
  artifacts.
- Stdlib only (Python 3.12), tanpa dependensi baru.
- Tidak ada endpoint detail run (keputusan Mirza 2026-07-22) — autopsi
  mendalam tetap lewat file artifacts langsung.
