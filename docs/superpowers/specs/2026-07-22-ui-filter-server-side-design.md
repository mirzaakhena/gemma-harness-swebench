# Desain: Filter Status Server-Side + Klik-Case di UI Log Viewer

Tanggal: 2026-07-22
Status: disetujui Mirza (sesi 2026-07-22, lanjutan API JSON)

## Tujuan

1. Filter All/PASS/FAIL di dashboard berlaku ke SELURUH data (server-side),
   bukan hanya menyembunyikan baris halaman aktif di frontend. Paging
   mengikuti hasil filter.
2. Filter status berlaku GLOBAL lintas tab (REPRODUCE/LOCALIZE/FIX and
   VERIFY) — dibawa saat pindah tab, persis perilaku filter nama case `q`.
3. Klik nama case di tabel → otomatis masuk filter "cari nama case"
   (`q=<case_id>`).
4. Bundle titipan final review API JSON: guard `per_page <= 0` di
   `paginate`, presisi wording spec API §3, test HTTP `status=%3F`.

## Desain

### Filter status server-side (`GET /?tab=&status=&q=&page=`)

- Param `status`: `PASS` | `FAIL`; nilai lain/kosong = All (fail-soft).
  Opsi UI tetap 3 (All/PASS/FAIL — keputusan Mirza 2026-07-22); WAIT/
  ANOMALY/? hanya terlihat lewat All.
- `page_index(root, tab, page, q, status)` dua-pass:
  - Pass 1 (semua run terfilter `q`): hitung `vtext`, `icon` (termasuk
    override f-* dan marker stale ➖), `status` baris via
    `_row_status_from_icon(icon)` — yang TAMPIL = yang DIFILTER.
  - Filter `status` → `paginate` → Pass 2 (baris halaman aktif saja):
    durasi, turns, started, link, tombol copy, modal alasan. Field mahal
    (console.log/turns) tidak dihitung untuk run di luar halaman.
- Panel ringkasan tetap dihitung SEBELUM filter status (angka stabil —
  konsisten semantik `summary` API).
- Radio jadi GET form auto-submit (`onchange=this.form.submit()`), membawa
  hidden `tab` + `q`. Link tab, pager, dan form search membawa `status`;
  link tab membawanya lintas kampanye (paritas perilaku `q`).
- JS `filterRows` + atribut radio lama dihapus (tak dipakai lagi).
- Baris info filter: bila `status` aktif tampil "filter status: <b>X</b> ·
  N run cocok" (pola sama dgn info filter case).

### Klik nama case

- Nama case kolom pertama jadi tautan `/?tab=<aktif>&q=<case_id>` +
  `status` aktif (bila ada). Tombol copy 📋 tetap di sebelahnya.

### Bundle final review

- `paginate`: `per_page = max(1, per_page)` di awal fungsi (hilangkan
  ZeroDivisionError bila pemanggil Python langsung memberi 0/negatif).
- Spec API §3 (`2026-07-22-ui-json-api-design.md`): wording `summary`
  dipresisikan → "dihitung SETELAH filter q, SEBELUM filter status dan
  paging".
- Test HTTP baru: `/api/runs?c=...&status=%3F` (enum `?` ter-URL-encode)
  → 200 dan hanya run berstatus `?`.

## Batasan

- Stdlib only, read-only, komentar Indonesia, baris baru ≤ 79 char —
  sama seperti sebelumnya.
- Perilaku tanpa param `status` harus identik dengan sekarang (regresi
  dijaga test page_index yang ada).
- API `/api/*` tidak berubah (UI-only), kecuali test tambahan.

## Testing

- `page_index` + `status=FAIL`: hanya baris FAIL tampil, jumlah halaman
  dihitung dari set terfilter (mis. 16 FAIL → hal 1/2 dgn PAGE_SIZE 15),
  run FAIL di "halaman 2 data penuh" muncul di halaman 1 hasil filter.
- Link pager & link tab membawa `status`; form search membawa hidden
  `status`; radio tercentang sesuai param.
- Nama case dirender sebagai link `?tab=..&q=<case_id>`.
- Tanpa `status`: keluaran identik perilaku lama (regresi).
- `paginate(per_page=0)` tidak crash.
- HTTP `status=%3F` → 200, hasil terfilter `?`.
