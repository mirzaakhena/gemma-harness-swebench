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
        "reasons": ["..."], "wall": "reproduce",
        "started": "2026-07-21 14:03"}]}

Catatan field:

- `verdict` = teks gabungan kolom verdict UI (verdict L1 + merge
  `gold_eval.json`; mis. `pass`, `wrong-file`, `pass (no-eval)`), BUKAN
  verdict.json mentah.
- `status`/`category`/`reasons` = `case_status()` run itu (di f-* sudah
  2-lapisan L1+L2).
- `wall` dari runs.jsonl event `end`: fase tempat run mentok (`reproduce|localize|fix|verify`) atau `"abort"`; `null` = tidak mentok / run hidup / legacy (kontrak: docs/kontrak-output.md §5).
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
- `500 {"error": "kesalahan internal server"}` — kegagalan internal tak terduga (fail-soft, koneksi tidak diputus).
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
