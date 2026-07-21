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

## KH-11 — "astropy-14365 gagal karena test noise-prone/flaky"

- **Yang dinyatakan:** sumber handoff menandai `astropy__astropy-14365` sebagai **noise-prone**;
  hipotesis awal (bot-03) menampung kemungkinan bahwa `resolved=false` disebabkan kegagalan F2P
  `test_qdp.py::test_roundtrip[True]` yang flaky, bukan patch model.
- **Derajat: TERBANTAH.**
- **Yang benar:** test-nya **deterministik penuh**, dan `resolved=false` sepenuhnya dijelaskan
  oleh **patch model = subset ketat gold** (menerapkan hunk-1 `re.IGNORECASE`, menghilangkan
  hunk-2 `if v.upper()=="NO":` di `_get_tables_from_qdp_file`).
- **Bukti pembantah — eksperimen (container `probe14365`, interpreter testbed, `__pycache__`
  dihapus tiap putaran, `PYTHONDONTWRITEBYTECODE=1`):** GOLD dipasang → `test_roundtrip[True]`
  **PASS 3/3**; patch MODEL → **FAIL 3/3**, error identik tiap kali
  (`could not convert string to float: 'no'` @ `qdp.py:316`). Nol variansi antar-jalankan.
  Bukti kausal tambahan: lokasi crash bergeser baseline `qdp.py:78` (hunk-1) → model
  `qdp.py:316` (hunk-2) — membuktikan hunk-1 model lolos, lalu mati tepat di titik yang hunk-2
  gold seharusnya perbaiki.
- **Pelajaran:** label "noise-prone" adalah klaim **tentang alat ukur** — SOP §3d/KH-07 mewajibkan
  MENJALANKANNYA, bukan menerimanya. Menjalankan gold berulang memisahkan "test flaky" dari
  "patch tak lengkap" dengan angka.

## KH-12 — "django-15851 gagal karena repro model ber-SyntaxError (analog LV-02)"

- **Yang dinyatakan (bot-03, read-awal ke subagent):** verdict `syntax-fail` 3/3 berarti model
  berulang kali menulis `repro.py` yang punya `SyntaxError`; kelas ini analog LV-02 (`py_compile`
  di titik tulis, tapi di fase REPRODUCE).
- **Derajat: TERBANTAH.**
- **Yang benar:** **tidak ada SyntaxError, dan tidak ada `repro.py` yang pernah ditulis.** `files/`
  ketiga run hanya berisi `pipe_runtime.py`. Model terjebak loop degeneratif: meng-emit token
  `<|tool_call|>` miliknya sendiri **tanpa fenced-block** ```` ``` ````, sehingga `parse_actions`
  menghasilkan **0 aksi** dan reply byte-identik diregenerasi 40 turn ×3 (temp 0.0). Verdict
  `syntax-fail` berasal dari `run_repro_gates.py:65-68` (`"required artifacts missing"`) —
  me-relabel "artefak tak diproduksi" jadi seolah kegagalan sintaks.
- **Bukti pembantah:** `files/` ketiga run tanpa `repro.py`; `console.log` r1 = 40 reply
  byte-identik dengan **nol** baris `[exec]`; `parse_actions` atas reply asli → `[]`,
  `has_fences=False` (r1/r3). Akar: mismatch protokol tool-call model↔driver +
  `format_reminder` yang dipagari `has_fences=True` (jadi mode kegagalan ini dapat pesan
  terlemah) + tak ada pemutus loop no-progress lepas dari `observed_fail`.
- **LV-02 tidak berlaku:** ia mengandaikan ada file yang ditulis untuk di-`py_compile`; di sini
  tak ada write. Dicatat sebagai temuan observability (B) di katalog batch bot-03, bukan LV-02.
- **Pelajaran:** JANGAN percaya label verdict sebagai diagnosa. `syntax-fail`/`wrong-logic`
  adalah bucket catch-all; buka artefaknya (`files/`, `console.log`, `parse_actions`) sebelum
  menamai sebab. Dua read-awal batch ini (KH-11, KH-12) terbantah justru karena awalnya percaya
  label/anotasi.

## KH-13 — "`gold_eval.line_overlap=false` berarti patch di baris yang salah"

- **Yang dinyatakan (bot-03, read-awal 12907):** `astropy-12907` punya `file_match=true` tetapi
  `line_overlap=false`, jadi patch model ada di **file benar, baris salah**.
- **Derajat: DIPERSEMPIT.**
- **Yang benar:** pada patch yang **me-rewrite file** (bukan hunk minimal), `line_overlap=false`
  bisa **false-negative**: patch model 12907 **memuat baris fix gold yang benar**
  (`cright[-right.shape[0]:, -right.shape[1]:] = right`), tetapi karena model menulis ulang
  seluruh modul (hunk pembuka `@@ -1,191 +1,55 @@`) penomoran baris bergeser total sehingga
  detektor overlap tak menemukannya. Kegagalan `resolved=false` bukan "baris salah" melainkan
  **kerusakan kolateral rewrite** (penghapusan API publik `is_separable` → ImportError di
  collection).
- **Bukti pembantah:** pembacaan `fix.diff` (baris `= right` hadir & benar) + `swebench_test_output.log`
  (`ImportError: cannot import name 'is_separable'`, `collected 0 items / 2 errors`).
- **Pelajaran:** `line_overlap` andal untuk patch hunk-minimal, TIDAK untuk patch rewrite.
  Sebelum menyimpulkan "baris salah" dari `line_overlap=false`, verifikasi kehadiran baris fix
  secara semantik di `fix.diff`.

## KH-14 — "`line_overlap=true` (+ `file_match=true`) membuktikan patch benar"

- **Yang dinyatakan (bot-04, read-awal utk django-11999):** karena `resolved=false` DENGAN
  `file_match=true` DAN `line_overlap=true`, kasus ini "file+baris benar tapi patch salah", dan
  bisa dikelompokkan bersama 14365 (`line_overlap=true` tapi subset) di bawah satu payung
  "line_overlap menyesatkan".
- **Derajat: DIPERSEMPIT** (dan arahnya BERLAWANAN dari yang kukira).
- **Yang benar:** `line_overlap=true` di sini **literal benar** (model memang mengedit region baris
  gold — hunk-1 `contribute_to_class` ≡ gold, `cls` in scope), TAPI **buta terhadap 3 hunk EKSTRA
  berbahaya** di file yang sama (`get_choices`/`Field.formfield`/`BooleanField.formfield`, guard
  disalin ke scope tanpa `cls` → `NameError: name 'cls' is not defined`). `resolved=false` **100%
  regresi P2P (9 gagal), 0% target-fail** — F2P `test_overriding_FIELD_display` justru **PASS**.
  Patch = **SUPERSET over-broad**, bukan subset. Detektor `line_overlap` menjawab "apakah baris gold
  tertutup?", **tak pernah** "apakah patch juga merusak di LUAR baris gold?".
- **Cermin 14365, arah kebalikan:** 14365 = subset/hunk HILANG → F2P **gagal**, `line_overlap=true`
  menutupi hunk yang absen. 11999 = superset/hunk EKSTRA → F2P **lulus**, P2P regresi,
  `line_overlap=true` menutupi hunk yang berlebih. Menggabungkan keduanya hanya via
  "`line_overlap=true` tapi `resolved=false`" **menyembunyikan dua mode kegagalan berbeda yang butuh
  dua detektor berbeda**. Konsekuensi konkret utk LV-14: hitung mismatch jumlah region hunk gold-vs-patch
  **DUA ARAH** (patch < gold DAN patch > gold di file yang sama), bukan hanya subset.
- **Bukti pembantah:** `swebench_test_output.log` (F2P `test_overriding_FIELD_display` PASS; 9 P2P
  `NameError: name 'cls' is not defined` dari `get_choices`/`formfield`); `fix.diff` (4 hunk vs
  `gold.patch` 1 hunk); hunk-1 identik-semantik gold (itu sebab `line_overlap=true` + F2P PASS).
- **Pelajaran:** `line_overlap=true`+`file_match=true` membuktikan **lokasi gold tersentuh**, BUKAN
  patch benar. Sebelum membaca hijau dari keduanya, cek jumlah/scope hunk di luar gold (superset) DAN
  di dalam gold (subset). Instans kedua bias "percaya sinyal lokasi sbg sinyal kebenaran" (bersama KH-13).

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

### Addendum 2026-07-21 (bot-03) — bias ketiga: percaya label verdict/anotasi

Dua koreksi batch bot-03 (**KH-11, KH-12**) berbentuk sama dan berbeda dari dua bias di atas:
**menerima label verdict atau anotasi sumber sebagai diagnosa, tanpa membuka artefaknya.**
`syntax-fail` dibaca sebagai SyntaxError (padahal artefak repro tak pernah ditulis); "noise-prone"
dibaca sebagai flaky (padahal test deterministik). Keduanya tumbang di detik artefaknya dibuka
(`files/`, `console.log`, `parse_actions`) atau alat ukurnya dijalankan (gold berulang). Penangkal
yang sama bekerja — subagent dengan izin membantah + eksperimen atas klaim-alat-ukur — dan
ditambah satu aturan konkret: **verdict REPRODUCE (`syntax-fail`/`wrong-logic`) adalah bucket
catch-all; perlakukan sebagai penunjuk, bukan sebab** (lihat temuan observability (B) di katalog
batch bot-03).

### Addendum 2026-07-21 (bot-04) — KH-12 dapat instansi ke-2 & ke-3 + sub-signature baru

**14855 & 15902** (batch A2 lanjutan, REPRODUCE-fail) = instansi kedua & ketiga pola KH-12
(`syntax-fail` = mislabel; 0 SyntaxError di 6 rerun; repro tak pernah ter-persist). **Sub-signature
BARU** yang membedakan dari 15851: di 15851 model emit `<|tool_call|>` **tanpa fence** (`format_reminder`
tak menyala); di 14855/15902 fence **ADA** tapi verb tulis-file salah-tag (` ```python ` alih-alih
` ```file: `) → `format_reminder` **menyala tapi tak efektif**. Ini **membantah** dugaan bahwa
`format_reminder` (calon fix yang diusulkan di KH-12) akan menyelamatkan: pesannya sudah terkirim,
model tetap gagal 40 turn ×3. Wall REPRODUCE **berlapis** — akar-MODEL primer (instruction-following),
dengan dinding kedua (repro logic buggy + `repro.md` tak ditulis 0/6). Detail + spec improvement label
(requirement Mirza: label harus identifikasi-gejala; mapping `syntax-error`/`repro-missing`/`vacuous-repro`/`gold-wont-flip`,
**BELUM DITERAPKAN**) di katalog batch A2 lanjutan.

### Addendum 2026-07-21 (bot-04) — "FIX-wall" bukan kelas homogen (DIPERSEMPIT)

Framing awal "7 backlog resolved=false = FIX-wall / yardstick longgar (LV-01)" **DIPERSEMPIT**.
Autopsi 9 backlog membuktikan: dari 7 fail hanya **1 (7746)** benar akar-repro-longgar (LV-01).
**2 (11797, 13158)** akar-LOCALIZE (file gold tak masuk kandidat, `file_match=false`) — bukan FIX
sama sekali. **1 (11910)** akar-MODEL + gate tak jalankan P2P (batas desain gate). **1 (13768)**
batas gold-blind (F2P brittle exact-string, unguessable). **2 (15320, 15400)** akar-MODEL murni
(patch salah-mekanisme / hallucinated). Pembantah: `file_match` + `f2p_failed`/`p2p_failed` +
`fix.diff` dibuka per case. **Pelajaran metodologi:** verdict "FIX gagal" adalah GEJALA; klasifikasi
lever HARUS by-AKAR (LOCALIZE-recall / repro-K4 / gate-P2P / model), bukan by-gejala — kalau tidak,
lever salah-arah di ~3 dari 4 case.

---

## KH-15 — "django-11564 REPRODUCE-wall = KH-10 Python 3.6 (`subprocess.run(text=)`)"

- **Yang dinyatakan (bot-02, papan grup-1, `katalog-lever.md` baris 3802):** `11564` = REPRODUCE-wall
  kelas **KH-10 Python 3.6** — *"`subprocess.run(text=...)` TypeError berulang, exec JALAN tapi
  crash API-version"*.
- **Derajat: DIPERSEMPIT** (plus salah-atribusi mekanisme churn).
- **Yang benar (dari rerun serial bot-03, artefak `r-dev--django__django-11564--r1` & `--r3`):**
  1. **TypeError-nya di `__init__`, bukan `subprocess.run`.** Semua `unexpected keyword argument` di
     r1/r3 berbentuk `__init__() got an unexpected keyword argument 'env'/'text'` = konstruktor
     **`pipe_runtime.App`** (halusinasi signature App), BUKAN `subprocess.run(text=/capture_output=)`.
     Per distingsi KH-10 sendiri, ini flavor **App-API-hallucination**, bukan flavor
     genuine-Python-3.6-subprocess. (`subprocess.run` akan berbunyi `run() got …`, bukan `__init__()`.)
  2. **API-churn BUKAN yang mem-wall r3.** Model pulih dari churn App-`env` dan mencapai DONE (turn
     18). Wall r3 = **judge (LV-05) memaksa checkpoint in-process (`RequestFactory`+`SCRIPT_NAME`,
     plausibel-flip) dibuang → orkestrasi WSGI-server**; peluncur `python3 -c` model **inline
     `try:`/`except` dgn `;`** → `SyntaxError` → repro always-FAIL (base DAN gold) → flip gagal →
     `wrong-logic`. Ditangkap flip gate (harness BENAR); gold **satisfiable**.
- **Bukti pembantah:** `console.log` r3 baris 483 (checkpoint in-process `repro-first-fail.py`),
  1718–1728 (judge deferral menuntut real WSGI server), 1873+ (pivot ke WSGI subprocess);
  `flip_run.json`/`gate_runs.json` r3 (base=FAIL/patched=FAIL, output = `SyntaxError` di child
  `python3 -c`); `grep "__init__.*unexpected keyword"` r1/r3 = semua di konstruktor App, **nol** `run(`.
- **Ruang lingkup:** bot-02 mengamati 11564 di grup-1 (konteks run berbeda); narrowing ini berbasis
  artefak rerun serial r1/r2/r3 bot-03. Mungkin grup-1 melihat run lain — karena itu **DIPERSEMPIT,
  bukan TERBANTAH**.
- **Pelajaran:** (i) kelompokkan REPRODUCE-wall **by-AKAR** bukan by-teks-error (addendum bot-04); satu
  case bisa berganti akar antar-rerun. (ii) `__init__(...)` vs `run(...)` di TypeError memisahkan
  App-hallucination dari Python-3.6-subprocess — jangan digabung (instansi bias "percaya label/teks
  error tanpa buka artefak", bersama KH-10/KH-12).

## KH-16 — "14155/12856/12184/13321/15202 REPRODUCE-wall = akar-MODEL (repro tak qualified)"

- **Yang dinyatakan (bot-03, papan skor grup-3 awal; bot-04, taksonomi §R-4 menaruh 14155/12184/13321 sbg kandidat akar-MODEL):** case-case ini mentok di REPRODUCE (`wrong-logic`/tak-qualified) karena repro model / model gagal.
- **Derajat: TERBANTAH** (reklasifikasi akar) untuk **5 case**, + sub-sebab BARU.
- **Yang benar:** `cases/gold/<id>/gold.patch` **MALFORMED di level PARSE** (body hunk kurang ≥1 baris konteks trailing vs header `@@ -a,b +c,d @@`). Flip runner (`repro_sandbox_runner.py:29`) menjalankan `git apply /patch-in/gold.patch && python repro.py`; `git apply` GAGAL "corrupt patch" → `&&` short-circuit → repro **tak pernah jalan** di gold-world → gate melihat "no REPRO_STATUS token in gold-patched run output" → verdict `wrong-logic`. **Base-world repro JALAN & `REPRO_STATUS: FAIL` benar.** Akar = **DATA-setup korup**, BUKAN akar-MODEL/repro. Scan seluruh korpus (`git apply --numstat` per patch): **5/97 django gold.patch korup — 12184, 12856, 13321, 14155, 15202** (15202 ada di grup-4).
- **Bukti pembantah (independen, bisa diulang):** `git apply --numstat cases/gold/django__django-14155/gold.patch` → `error: corrupt patch at line 22` (error PARSE, sebelum menyentuh tree apa pun; sama utk 12856@15, 12184@14, 13321@19, 15202@41). `flip_run.json` = `{"output":"error: corrupt patch at line N","exit":128}`. `gate_runs.json` base = repro bekerja.
- **Pelajaran:** verdict `wrong-logic` bisa lahir dari **gold-data-corrupt**, bukan hanya model/repro salah. Instansi ke-N bias-3 ("percaya label verdict") dengan **sub-sebab BARU**: data-setup korup. Kandidat lever KL-G3-1 = **validasi `git apply --check gold.patch` saat prepare_cases** (fail-fast). **Konsekuensi:** taksonomi bot-04 §R-4 perlu revisi — 5 case ini KELUAR dari tally akar-MODEL; wall-nya vacuous sampai gold diperbaiki.

## KH-17 — "`skipped-fix-localize-miss` = LOCALIZE-recall gagal (salah-file, Kelas-A)"

- **Yang dinyatakan (bot-03, papan skor grup-3 awal):** semua case ber-`error=skipped-fix-localize-miss` = Kelas-A akar-LOCALIZE (model gagal me-localize file gold).
- **Derajat: DIPERSEMPIT.**
- **Yang benar:** kriteria prune (`should_prune_fix`, `run_rlfv_batch.py:113`) me-return `gold_eval["file_match"] is False` — di-key ke **`file_match`** (apakah *pointed_file primer* == gold). Tapi kriteria qualify/FIX-iterasi di-key ke **`qualified`** (apakah *ada* file di shortlist ∈ gold; FIX mengiterasi seluruh shortlist). Dua kriteria INKONSISTEN. **13033:** `pointed_file=sql/query.py` (`file_match=false`) TAPI candidate-2 `sql/compiler.py` = **GOLD** → `qualified=true`. Recall LOCALIZE **SUKSES** (gold tersedia utk FIX), tapi tetap di-skip. Jadi `skipped-fix-localize-miss` **mencampur** (a) recall-miss sejati (15213/12589) DAN (b) **false-prune** (recall sukses, prune over-agresif) — bukan homogen Kelas-A.
- **Bukti pembantah:** 13033 `l-dev/.../gold_eval.json` = `file_match=false ∧ qualified=true`; `should_prune_fix` keys `file_match`. **Bukti bahaya:** `11620` bersignature `file_match=false ∧ qualified=true` **DAN `resolved=true`** — prune (bila dipakai saat itu) akan meng-skip case yang justru RESOLVED.
- **Pelajaran:** label `error` batch ≠ diagnosa akar. Papan skor "Kelas-A" tercemar false-prune. Kandidat lever KL-G3-2 = **prune keying `qualified` (bukan `file_match`)**, konsisten dgn kriteria FIX-iterasi.
