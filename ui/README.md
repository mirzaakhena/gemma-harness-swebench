# UI Log Viewer

Viewer log run harness — sengaja sederhana: HTML polos + auto-refresh 3 detik,
stdlib Python saja (tanpa dependency, tanpa build step). Baca-saja terhadap
`artifacts\` (kontrak: `docs\kontrak-output.md`).

## Menjalankan

```
python ui\server.py
```

Default: root `..\artifacts` (relatif repo main), port 8766, bind 127.0.0.1.
Override:

```
python ui\server.py --root D:\path\ke\artifacts --port 8888
```

Lalu buka <http://127.0.0.1:8766/>.

## Halaman

- `/` — daftar campaign → daftar run (dari `runs.jsonl`, fallback listing
  direktori) + verdict ringkas bila `verdict.json` ada.
- `/run?c=<campaign>&r=<run_id>` — tail `events.jsonl` (satu baris per event:
  ts, phase, event, verdict, attempt, detail singkat) + tail `console.log`
  mentah. Default 200 baris terakhir; ubah via `&n=500`. Auto-refresh tiap
  3 detik lewat meta refresh — itulah "live"-nya.

## Catatan

- File belum ada / JSON rusak → ditampilkan apa adanya, tidak crash.
- Parameter `c`/`r` divalidasi ketat (`[A-Za-z0-9_.-]`, tanpa `..`) — anti
  path traversal.
- Logika inti (`list_campaigns`, `list_runs`, `tail_lines`,
  `render_event_line`, `validate_name`) dites di `tests\test_ui_core.py`.
