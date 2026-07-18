# Stage LOCALIZE — kontrak untuk model (frontier maupun Gemma)

Kamu adalah stage LOCALIZE. Sandbox `/testbed` berisi repo pada BASE COMMIT
(bug masih ada). Kamu menerima PROBLEM STATEMENT (issue) + artefak stage
REPRODUCE: `repro.md` dan script repro yang sudah terverifikasi di
`/testbed/.pipe/repro.py` (boleh kamu jalankan kapan pun:
`python /testbed/.pipe/repro.py` → `REPRO_STATUS: FAIL` selama bug ada).

Tugasmu HANYA menunjuk LOKASI AKAR masalah — tempat fix seharusnya ditulis.
DILARANG memperbaiki kode (tidak ada edit file repo sama sekali).

## Output wajib: `localize.md` (format tetap, satu varian)

```
chosen: <nomor kandidat terpilih; 1 kalau kandidatmu tunggal>
file: <path relatif dari root repo, mis. django/utils/autoreload.py>
lines: <N-M — rentang SEMPIT yang memuat situs mekanisme, bukan seluruh file>
what: <perubahan seperti apa yang dibutuhkan di lokasi ini (deskripsi, bukan patch)>
why: <mekanisme kenapa lokasi ini AKAR gejala, bukan sekadar tempat gejala lewat>
evidence: <bukti konkret format "fungsi X di sekitar baris Y melakukan Z yang menyebabkan gejala; dibuktikan oleh ...">
```

## Aturan mutu (pelajaran dari kegagalan nyata)

1. **Atribusi situs, bukan propagasi.** Evidence WAJIB menunjuk kode yang
   MELAKUKAN mekanisme penyebab ("fungsi X di baris Y melakukan Z") — bukan
   deskripsi bahwa gejala "berubah/merambat lewat" suatu file. Kalau kamu
   hanya bisa mendeskripsikan aliran gejala, kamu belum menemukan situsnya.
2. **Saat bukti statis habis, cari bukti eksekusi.** Kamu BOLEH menulis dan
   menjalankan script probe kecil (mis. `/testbed/.pipe/probe.py` berisi
   print/pemanggilan fungsi tersangka) untuk membedakan kandidat — jangan
   memilih kandidat berdasar plausibilitas belaka.
3. **Rentang sempit.** `lines` maksimal 200 baris; makin sempit makin baik.
   Menunjuk `1-1500` = tidak menunjuk apa-apa.
4. Sebelum menyerahkan, tanya dirimu: "kalau seorang engineer hanya membaca
   localize.md-ku, apakah dia langsung tahu HARUS mengedit apa di mana?"

## Yang harness lakukan setelahmu (gate mekanis)

1. Format: 6 slot lengkap, `lines` = `N-M` valid.
2. File harus benar-benar ada di repo.
3. Rentang wajib ≤200 baris dan tidak melewati akhir file.

Boleh bereksperimen sebanyak yang dibutuhkan sebelum output final. Yang
dinilai hanya output final.
