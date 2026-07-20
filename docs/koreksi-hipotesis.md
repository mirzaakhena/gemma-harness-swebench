# Koreksi Hipotesis — gemma-harness-swebench

Dibuat 2026-07-20 (bot-01). Dokumen internal, bahasa Indonesia.

## Tujuan

File ini mencatat **hipotesis yang pernah kami pegang lalu dibantah**, beserta bukti
pembantahnya. Bukan daftar kesalahan untuk disesali — daftar ini punya tiga kegunaan
operasional:

1. **Mencegah klaim mati dikutip ulang.** Tanpa catatan ini, kesimpulan yang sudah
   gugur tetap hidup di commit message lama, di ringkasan chat, dan di kepala orang
   yang membacanya sekali.
2. **Menyimpan METODE pembantahnya.** Beberapa koreksi di bawah lahir dari teknik yang
   ternyata berlaku umum (mis. eksperimen sabotase untuk mengukur daya beda sebuah
   test). Metodenya lebih berharga daripada koreksi tunggalnya.
3. **Menunjukkan arah kalibrasi.** Pola kesalahan kami konsisten: **terlalu cepat
   menyimpulkan kausalitas dari korelasi, dan terlalu cepat menamai sesuatu sebagai
   kelas baru.** Mengetahui bias sendiri lebih murah daripada menemukannya berulang.

## Aturan main

1. **Append-only.** Entri baru di bawah, ID berikutnya. Jangan mengedit entri lama.
2. **Wajib menyebut bukti pembantah**, bukan sekadar "ternyata salah". Kalau
   pembantahnya eksperimen, tulis cukup detail supaya bisa diulang.
3. **Bedakan tiga derajat**: TERBANTAH (dibuktikan salah), TIDAK DIDUKUNG (bukti tidak
   cukup, belum tentu salah), dan DIPERSEMPIT (klaimnya benar tapi lebih sempit dari
   yang dinyatakan). Menyamakan ketiganya adalah kesalahan tersendiri.
4. **Catat siapa yang membantah.** Sebagian besar koreksi di bawah datang dari subagent
   yang diminta memverifikasi ulang klaim pemanggilnya — itu mekanisme yang bekerja dan
   layak dipertahankan.

---

## KH-01 — "Repro 11910 tidak deterministik lintas dunia"

- **Yang dinyatakan (bot-01, 2026-07-20):** script `repro.py` yang sama berperilaku
  berbeda antara dunia gate dan dunia kerja fase FIX, jadi repronya flaky.
- **Derajat: TERBANTAH.**
- **Yang benar:** kedua dunia deterministik. Yang berbeda adalah **isinya** — ada file
  yang tidak dikirim. `run_reproduce_gemma.py:286` dan `repro_sandbox_runner.py:35-36`
  mengirim `pipe_runtime.py`; `run_fix_gemma.py:231-232` hanya menulis `repro.py`.
  Repro 11910 mengimpor `from pipe_runtime import App` di baris 5, jadi di fase FIX ia
  mati di baris pertama.
- **Bukti pembantah:** pembacaan kode ketiga titik di atas, plus `gate_runs.json` yang
  menunjukkan dua run gate identik dan bersih (2 migrasi terbentuk, `REPRO_STATUS: FAIL`,
  exit 0). Terukur 588 `ModuleNotFoundError` di `f-dev--11910--r1`.
- **Pelajaran:** "perilaku berbeda" jangan langsung dibaca sebagai non-determinisme.
  Periksa dulu apakah kedua dunia benar-benar berisi hal yang sama.
- **Menjadi:** LV-09.

## KH-02 — "Bug pipe_runtime melemahkan validitas vonis fase FIX"

- **Yang dinyatakan (subagent autopsi 12286):** karena model kehilangan repro dan sempat
  memvalidasi diri dengan script buatannya sendiri, sinyal "repro lulus" di fase FIX
  berasal dari script model, sehingga validitas fase FIX melemah.
- **Derajat: TERBANTAH** (overclaim).
- **Yang benar:** yang rusak adalah **loop iterasi**, bukan **validitas vonis**.
  Pre-check DONE dan gate memakai fungsi yang sama (`evaluate_patch_in_fresh_world`)
  dengan argumen yang sama (`args.input_repro_files` = direktori artefak beku), dan
  `repro_sandbox_runner.py:25-37` menyalin `repro.py` **dan** `pipe_runtime.py` dari
  `/pipe-in:ro`. DONE hanya diterima ketika repro BEKU lolos di dunia segar yang lengkap.
- **Bukti pembantah:** `run_fix_gemma.py:30,303-305`, `run_fix_gates.py:23,88`,
  `repro_sandbox_runner.py:25-37`.
- **Pelajaran:** desain "standar tunggal" di arsitektur ini justru bekerja sebagaimana
  dimaksud. Sebelum menyimpulkan sebuah vonis cacat, telusuri jalur vonisnya sampai
  fungsi yang benar-benar dipanggil.
- **Menjadi:** klarifikasi bertanggal di Status LV-09 dan LV-11.

## KH-03 — "Gate menyeleksi repro yang lebih permisif"

- **Yang dinyatakan (bot-01, dari 11039):** repro r1 punya penjaga `if stderr: ... `
  tanpa `REPRO_STATUS`, r2 menghapusnya dan justru lolos; jadi gate cenderung meloloskan
  repro yang lebih longgar.
- **Derajat: TIDAK DIDUKUNG.**
- **Yang benar:** r1 gugur karena **predikat gold-unsatisfiable** (backend sintetis
  dengan `features` sebagai class attribute, ditimpa `BaseDatabaseWrapper.__init__`),
  sama sekali bukan karena penjaganya. Dan r2 adalah run segar tanpa memori, jadi bukan
  "belajar jadi permisif".
- **Rumusan yang sah dan lebih sempit:** loop retry menggeser distribusi bentuk repro ke
  arah permisif, dan karena kita rerun-sampai-qualified, script beku adalah sampel dari
  distribusi yang sudah bergeser. Itu klaim yang jauh lebih lemah dari aslinya.
- **Bukti pembantah:** `detail.why` gate r1 dan pembacaan `repro.py` r1 vs r2.
- **Pelajaran:** kalau dua hal berubah bersamaan (penjaga hilang DAN hasil berubah),
  jangan pilih yang paling menarik sebagai sebab.

## KH-04 — "Judge menggugurkan run"

- **Yang dinyatakan (implisit di beberapa laporan, termasuk milik bot-01):** penolakan
  judge adalah penyebab kegagalan run, jadi LV-05 dibenarkan oleh laju kegagalan.
- **Derajat: TIDAK DIDUKUNG** (di tingkat agregat).
- **Yang benar:** dari 20 run yang ditahan judge, **12 tetap qualified (60%)**,
  dibanding laju korpus **54%**. Run yang ditahan judge tidak lebih sering gagal.
  `11039` r1 adalah satu-satunya kegagalan yang bisa ditunjuk langsung ke judge.
- **Konsekuensi:** LV-05 tetap layak, tapi **argumennya harus ongkos-turn dan
  risiko-ekor**, bukan laju kegagalan. Ongkosnya nyata dan besar (mis. 16 dari 26 turn
  di 12915 r1 lahir setelah penolakan judge).
- **Pelajaran:** lever yang benar bisa dibela dengan alasan yang salah. Alasan yang
  salah akan runtuh saat diuji, dan menyeret levernya ikut runtuh.

## KH-05 — "Pola `else: PASS` adalah masalah mayoritas"

- **Yang dinyatakan (bot-01):** banyak repro memakai `if <gejala>: FAIL else: PASS`
  sehingga kegagalan katastrofik dilaporkan lulus — dan itu masalah luas.
- **Derajat: DIPERSEMPIT.**
- **Yang benar:** pola sintaktisnya memang 10 dari 23 case, **tetapi hanya 3 dari 23
  (13%)** yang benar-benar membuat kegagalan katastrofik mendarat di PASS. 7 dari 10
  punya penjaga exception yang membelokkan crash ke FAIL.
- **Bukti pembantah:** pemeriksaan manual 23 repro qualified (1.630 baris); detektor AST
  otomatis over-count dan angkanya dibuang.
- **Pelajaran:** pola sintaktis bukan pola perilaku. Hitung yang kedua, bukan yang pertama.

## KH-06 — "13658 lolos karena konstanta hardcoded yang kebetulan cocok"

- **Yang dinyatakan (bot-01):** patch model lolos F2P karena fallback `"django-admin"`
  yang di-hardcode kebetulan sama persis dengan string yang di-assert test.
- **Derajat: TERBANTAH.**
- **Yang benar:** konstanta itu **bukan sebab kelulusan**. String yang di-assert
  (`usage: django-admin shell`) diproduksi parser **sub-command** (`base.py:280`), yang
  sudah menerima `prog` dengan benar bahkan di base yang belum dipatch. Bug-nya ada di
  parser **top-level** (`__init__.py:347`). Test gagal di base karena **crash**
  (`basename(None)` → TypeError), bukan karena string-nya salah.
- **Bukti pembantah — eksperimen sabotase (bisa diulang):** pasang patch
  `prog='ZZZ-NGAWUR'` di titik gold, membaca nol dari argv → F2P **tetap lulus**.
  Base + test patch → FAILED. Kesimpulan: daya beda F2P `test_program_name_from_argv`
  seluruhnya **crash-vs-tidak-crash**, padahal docstring-nya mengklaim menguji "program
  name computed from argv, not sys.argv".
- **Metode yang lahir dari sini:** **eksperimen sabotase** — pasang patch yang jelas
  ngawur di titik yang benar, lalu lihat apakah test tetap lulus. Ini mengukur daya beda
  sebuah test secara empiris. Berlaku untuk F2P mana pun, dan (lihat KH-07) untuk repro.
- **Menjadi:** instansi kedua "batas metodologi", bukan kelas baru.

## KH-07 — "Kelemahan repro bersifat struktural/teoretis"

- **Yang dinyatakan (implisit):** analisis kualitas repro berbasis pembacaan kode —
  "fix under-general SEHARUSNYA bisa lolos repro ini".
- **Derajat: DIPERSEMPIT menjadi jauh lebih kuat** (koreksi ke arah sebaliknya: kami
  meremehkan, bukan melebih-lebihkan).
- **Yang benar:** kelemahannya bukan teoretis. Diuji langsung di container `14238` dengan
  interpreter testbed (`/opt/miniconda3/envs/testbed/bin/python`):
  - Baseline tanpa patch → `REPRO_STATUS: FAIL` (benar)
  - `__subclasscheck__` diganti `return True` (merusak total semantik tipe) → **PASS**
  - Gold fix benar TAPI `QuerySet.create()` disabotase raise → **PASS**
  - File repo ditinggalkan `SyntaxError` → **PASS**
  - Django sama sekali tidak bisa di-import → **PASS**
- **Pelajaran:** untuk klaim tentang alat ukur, **jalankan alat ukurnya** terhadap input
  yang sengaja rusak. Membaca kodenya menghasilkan klaim yang benar tapi lemah;
  menjalankannya menghasilkan angka yang tidak bisa didebat.

## KH-08 — "Patch 12286 salah untuk kode bahasa tiga komponen"

- **Yang dinyatakan (bot-01):** patch model (`split('-', 1)[0]`, fallback satu tingkat)
  salah untuk kode tiga komponen seperti `zh-hant-hk`.
- **Derajat: DIPERSEMPIT.**
- **Yang benar:** F2P resmi memuat `ca-ES-valencia` dan `LANGUAGES` di test itu memuat
  `('ca', 'Catalan')`, jadi `split('-',1)[0]` mendarat benar dan model lolos. Divergensi
  sesungguhnya muncul ketika yang terdaftar adalah **varian antara, bukan bahasa dasar**:
  `LANGUAGES=[('zh-hans', …)]` dengan `LANGUAGE_CODE='zh-hans-x'` — gold menerima
  (menelusuri ke `zh-hans`), model menolak (`zh` tidak terdaftar). Tidak ada test resmi
  yang membangun konfigurasi itu.
- **Pelajaran:** versi yang benar justru **memperkuat** kesimpulan (divergensi tetap
  fungsional dan bisa dibuktikan dengan satu contoh input). Klaim yang dipersempit
  dengan jujur sering lebih kuat daripada klaim besar yang rapuh.

## KH-09 — "Rasio pipe_runtime menunjukkan dampak kausal"

- **Yang dinyatakan:** repro ber-`pipe_runtime` 1 dari 5 resolved vs repro bersih 6 dari
  7 resolved — jadi bug LV-09 menurunkan laju keberhasilan.
- **Derajat: TIDAK DIDUKUNG** (sebagai klaim kausal).
- **Yang benar:** **3 dari 5** anggota kelompok terpapar adalah `13660`, yang gagal
  karena `exec(cmd, {})` — sama sekali bukan karena modul hilang. Rasio itu praktis
  mengukur satu case yang diulang tiga kali.
- **Pelajaran:** cek komposisi kelompok sebelum membaca rasio. n kecil dengan run
  berulang dari case yang sama bukan n yang sebenarnya.

## KH-10 — "`capture_output` / `text` adalah halusinasi API App"

- **Yang dinyatakan:** kemunculan `unexpected keyword argument 'capture_output'` dan
  `'text'` dihitung sebagai halusinasi API `pipe_runtime.App`.
- **Derajat: TERBANTAH** untuk sebagian kejadian.
- **Yang benar:** di `11039` model mendiagnosis sendiri dengan benar bahwa testbed
  memakai **Python 3.6**, di mana `subprocess.run` memang belum punya `capture_output`
  (3.7+) dan `text` (3.7+). Itu bukan halusinasi API `App` melainkan asumsi versi Python.
- **Konsekuensi:** menutup kandidat lever "Python 3.6" yang sempat menggantung —
  syaratnya terpenuhi (5 case, 30 kejadian) tetapi vonisnya tetap bukan entri baru,
  karena kedua pembacaan bermuara pada usulan LV-06 yang sama persis.
- **Pelajaran:** satu pesan error yang sama bisa punya dua sebab yang berbeda. Kelompokkan
  berdasarkan sebab, bukan berdasarkan teks errornya.

---

## Pola kesalahan kami (per 2026-07-20)

Dari sepuluh entri di atas, dua bias muncul berulang:

- **Melompat dari korelasi ke kausalitas** (KH-03, KH-04, KH-09). Semuanya berbentuk
  sama: dua hal terjadi bersamaan, kami menunjuk yang paling menarik sebagai sebab,
  tanpa memeriksa komposisi kelompok atau sebab alternatif.
- **Terlalu cepat menamai kelas baru** (KH-06, dan berkali-kali ditolak oleh analis
  berikutnya). Menamai sesuatu terasa seperti kemajuan padahal sering hanya
  memindahkan label.

Penangkal yang terbukti bekerja, dan sebaiknya dipertahankan:

- **Meminta subagent berikutnya memverifikasi ulang klaim pemanggilnya**, dengan izin
  eksplisit untuk membantah. Enam dari sepuluh koreksi di atas lahir dari situ.
- **Bar tinggi untuk entri baru** di katalog lever, plus kewajiban mencatat kandidat
  yang ditolak beserta syarat kapan boleh dinaikkan.
- **Eksperimen, bukan pembacaan**, untuk klaim tentang alat ukur (KH-06, KH-07).
