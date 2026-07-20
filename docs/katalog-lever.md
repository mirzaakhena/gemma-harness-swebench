# Katalog Lever — gemma-harness-swebench

Dibuat 2026-07-20 (bot-01). Dokumen internal, bahasa Indonesia.

## Tujuan

File ini adalah **daftar lever yang bisa dikoleksi lintas waktu**: tiap perbaikan mekanis
yang diusulkan untuk harness dicatat sebagai satu entri ber-ID, lengkap dengan asal-usul
(run bukti), diagnosa, usulan konkret, dan status vonisnya. Bedanya dengan dokumen tetangga:

- `docs/prinsip-pengembangan.md` — prinsip umum, bukan daftar aksi.
- Vault: `Asal-usul Rule & Lever — katalog cerita.md` — **retrospektif naratif** untuk lever
  yang SUDAH terpasang (bahan presentasi, punya commit). File ini melengkapinya dari sisi
  depan: lever yang belum diputuskan atau belum dipasang.
- Vault: `P25 — Backlog & Divergence Retrospective.md` — backlog proyek lintas fase
  (termasuk item non-lever seperti re-run dan koordinasi antar-bot).

## Aturan main

1. **Append-only.** Entri baru ditambahkan di bawah, dengan ID berikutnya. Jangan
   menyisipkan di tengah dan jangan memakai ulang ID.
2. **Jangan mengedit riwayat entri yang sudah divonis.** Kalau sebuah lever sudah berstatus
   DITERAPKAN / DITOLAK / GUGUR, isinya beku. Perkembangan baru ditulis sebagai baris
   tambahan di bagian Status entri itu (bertanggal), bukan dengan menulis ulang diagnosa lama.
3. **Status boleh maju, tidak boleh dihapus.** BELUM DITERAPKAN → DITERAPKAN (+commit) →
   (kalau hasilnya nihil) GUGUR. Lever yang gugur tetap tinggal — rangkaian nol adalah bukti,
   bukan aib (lihat L#1–L#3 di fase LOCALIZE).
4. **Satu mekanisme = satu lever.** Case kedua dengan tanda tangan kegagalan yang sama
   ditambahkan sebagai *bukti penguat* di entri yang ada, bukan sebagai entri baru.
5. **Prinsip induk: fisika > instruksi.** Usulan diutamakan kalau mengikat secara mekanis di
   titik vonis (gate / driver / API / kontrak eksekusi). Bukti proyek konsisten: perbaikan
   prompt ±17% efektif, dan L#1/L#2/L#3 di LOCALIZE nol efek. Lever yang isinya "tambah
   kalimat ke prompt" harus punya alasan khusus kenapa jalur mekanis tidak mungkin.
6. **Bedakan tegas akar-model vs akar-harness** di bagian Diagnosa. Lever yang menyerang akar
   yang salah adalah cara termahal untuk belajar.

---

## LV-01 — Perketat repro agar menguji jalur global-name-resolution

- **Asal-usul:** django-13660. Dicatat sebelumnya (sesi bot-05, 2026-07-20) di vault
  `F-dev Log — fase FIX`, bagian "HASIL — perbaikan prompt GAGAL menyelesaikan".
  Bukti: `l-dev--django__django-13660--r4`, `f-dev--django__django-13660--r3`
  (`swebench_eval.json` resolved=false).
- **Gejala:** FIX Gemma menulis `exec(cmd, {})` alih-alih `exec(cmd, globals())`. Repro
  lolos (flip OK) karena hanya menguji jalur inline, sedangkan P2P resmi menguji resolusi
  nama global. Checker L2 resolved=FALSE dengan p2p_failed identik
  (`test_command_option_globals`, `test_stdin_read_globals`).
- **Bukti penguat (case kedua, independen) — django-14017**, run
  `f-dev--django__django-14017--r1` (temuan bot-01, 2026-07-20): `repro.py` hanya mengecek
  bahwa `Q() & Exists()` tidak melempar `TypeError`, tanpa memeriksa struktur hasilnya.
  Gemma menulis fix khusus `Exists` + early-return yang melewati handling `Q` kosong.
  L1 flip PASS, gold_eval file_match + line_overlap TRUE, tetapi checker L2 resolved=false:
  F2P 0/2 gagal dan 1 regresi P2P (`test_case_in_filter_if_boolean_output_field`).
  **Tanda tangan sama:** repro menguji *gejala permukaan* (tidak crash / tidak NameError),
  bukan *kontrak yang dilanggar*; fix sempit yang mematikan gejala lolos gate.
- **Bukti penguat (sisi sebaliknya — HIJAU pun tidak membuktikan apa-apa) — django-11099**,
  run `r-dev--django__django-11099--r1` + `f-dev--django__django-11099--r1`
  (temuan bot-01, 2026-07-20). Ini satu-satunya run full green di korpus
  (`swebench_eval.json` resolved=true, F2P 3/3, P2P 19/19), tapi buktinya lemah:
  gold hanya mengganti anchor BELAKANG (`^...$` → `^...\Z`) di `ASCIIUsernameValidator`
  dan `UnicodeUsernameValidator`; Gemma mengganti KEDUA anchor (`\A...\Z`); sementara
  `files/repro.py` hanya menguji empat kasus trailing-`\n`/tanpa-`\n` dan **tidak pernah
  menyentuh anchor depan sama sekali**. Artinya fix minimal (`$`→`\Z` saja) lolos repro,
  fix Gemma yang lebih ketat juga lolos repro, dan repro tidak bisa membedakan keduanya.
  Hijau di sini didapat karena **ruang fix-nya kebetulan sempit** (satu regex, satu file),
  bukan karena yardstick-nya menggigit. Konsekuensi untuk pembacaan papan skor: repro
  longgar bukan cuma meloloskan fix salah (13660, 14017) — ia juga membuat hasil BENAR
  tidak bisa dipakai sebagai bukti bahwa gate bekerja. Jangan hitung 11099 sebagai
  validasi yardstick.
- **Bukti penguat (case ketiga, full green — predikat proksi di boundary internal) —
  django-13230**, run `r-dev--django__django-13230--r1/files/repro.py` +
  `f-dev--django__django-13230--r1` (temuan bot-01, 2026-07-20). Run ini FULL GREEN
  (`resolved=true`, F2P 1/1 `test_rss2_feed`, P2P 23/23) dan patch modelnya setara semantik
  dengan gold (baris `comments=self._get_dynamic_attr('item_comments', item),` identik, hanya
  beda posisi sisip antar keyword argument). Tetapi repro-nya **tidak pernah memeriksa keluaran
  yang dilihat user**: ia me-monkeypatch `SyndicationFeed.add_item`, menangkap `kwargs`, lalu
  meng-assert `kwargs['comments'] == "http://comments/1/"`. Test resmi `test_rss2_feed`
  memeriksa **XML** hasil akhir; repro berhenti satu lapis di dalamnya. Konsekuensinya, fix yang
  meneruskan `comments` ke `add_item` tetapi merusak emisi elemen `<comments>` di XML akan
  **lolos repro dan gagal test resmi**. Kelemahan tambahan di script yang sama: `item_comments`
  hanya diuji sebagai *method*, tidak pernah sebagai atribut statis (padahal kontrak
  `_get_dynamic_attr` mendukung keduanya); tidak ada kontrol positif yang ikut menentukan
  kelulusan; dan `except TypeError:` di sekeliling `view(request)` cukup lebar untuk menelan
  `TypeError` asli dari dalam pipeline feed, lalu diam-diam jatuh ke jalur fallback.
  **Tanda tangan sama dengan 11099:** hijau di sini diperoleh karena ruang fix-nya kebetulan
  sempit (satu baris, satu call site yang sudah ditunjuk), bukan karena yardstick-nya menggigit.
  Catatan penting soal sebab: bentuk monkeypatch itu **bukan pilihan awal model** — checkpoint
  `files/repro-first-fail.py` memeriksa `feed_gen.items[0]['comments']` langsung dari objek
  feed generator, tanpa monkeypatch dan tanpa `except` lebar, dan itu sudah exec-pair hijau.
  Bentuk yang lebih longgar lahir setelah penolakan judge (lihat bukti penguat di LV-05).
- **Diagnosa:** dua lapis.
  - *Akar-model* pada pilihan fix-nya sendiri (`{}` vs `globals()`; early-return khusus
    `Exists`) — pemahaman semantik, dan terbukti muncul konsisten & independen di LOCALIZE
    maupun FIX, jadi bukan sekadar anchoring prompt.
  - *Akar-harness* pada **yardstick**: gate menerima repro yang under-specified, sehingga
    fix yang salah tetap lolos vonis. Selama repro longgar, tidak ada gaya mekanis apa pun
    yang mendorong model ke fix yang benar.
- **Usulan lever:** perkuat repro sebagai alat ukur, di titik vonis — bukan di prompt.
  Arah yang sudah dicatat: repro wajib menguji jalur yang dilanggar (global-name-resolution
  untuk 13660), sehingga `exec(cmd, {})` GAGAL repro → gate menolak → model dipaksa mencari
  fix yang benar-benar lolos. Bentuk mekanis konkretnya masih perlu spec (lihat Catatan).
- **Status:** BELUM DITERAPKAN.
- **Prioritas:** UTAMA. Naik dari rendah ke utama berdasar eksperimen prompt-only yang
  dibantah; kini diperkuat case kedua (14017) yang independen dari 13660.
- **Catatan:** desain generiknya belum tuntas — "perketat repro" mudah dikatakan, sulit
  dimekaniskan tanpa membocorkan gold. Kandidat arah yang tidak melanggar boundary: turunkan
  syarat repro dari *issue text* (perilaku yang user demonstrasikan), bukan dari test resmi.

## LV-02 — Validasi syntax saat driver FIX menulis file (`py_compile`)

- **Asal-usul:** dicatat sebelumnya (backlog FIX). Konteks pendukung di vault
  `Arsip Harness/pipeline_journey.md` dan `Pipeline v2 — Stage Isolation Plan.md`.
- **Gejala:** edit FIX yang menghasilkan file tidak valid / rusak diterima driver dan baru
  ketahuan jauh di hilir.
- **Bukti penguat (case pertama dengan angka keras) — django-11910 attempt 2**, run
  `f-dev--django__django-11910--r1`, artefak `files/attempts/attempt-2.diff`
  (temuan bot-01, 2026-07-20). Gemma menulis `related.py` lewat script Python
  cari-dan-sisip yang bugnya jelas (`i += 5` di dalam `while` yang mencocokkan
  `def deconstruct(self):`), hasilnya blok yang sama disisipkan **23×** berturut-turut
  dengan indentasi invalid (`return name, path, args, kwargs` di kolom 8 diikuti
  `if ...` di kolom 12) sehingga `related.py` **tidak bisa di-parse lagi**. Driver
  menerima tulisan itu tanpa protes (`docker_write_file` di `run_fix_gemma.py` tidak
  memvalidasi apa pun), dan attempt 2 kemudian menghabiskan **seluruh 40 turn** tanpa
  pernah menjalankan repro sekali pun. `py_compile` di titik tulis akan memotong ini
  di turn pertama, bukan di turn ke-40. Catatan: di run ini kerusakan syntax bukan
  penyebab tunggal kegagalan (lihat LV-09); tapi ia adalah kelas yang persis ditutup
  lever ini, dan ini bukti langsung pertamanya dengan artefak.
- **Diagnosa:** akar-harness murni (validasi yang absen di titik tulis).
- **Usulan lever:** driver FIX menjalankan `py_compile` atas file hasil tulis; gagal compile
  → revert per-file + feedback ke model.
- **Status:** BELUM DITERAPKAN.
- **Prioritas:** sedang.
- **Catatan penting (jangan overclaim):** `py_compile` hijau TIDAK berarti benar. Sudah ada
  kasus tercatat di mana edit valid secara sintaks tapi meninggalkan body lama *unreachable*
  setelah `continue` — compile bersih, test tetap gagal, plus 3 regresi. Lever ini menutup
  kelas "file rusak", bukan kelas "logika salah".

## LV-03 — Samakan himpunan file antara pagar edit dan ekstraksi diff

- **Asal-usul:** dicatat sebelumnya (backlog FIX).
- **Gejala:** file untracked lolos pagar edit — pagar dan ekstraksi diff bekerja atas
  himpunan file yang berbeda, sehingga ada celah.
- **Bukti penguat — django-11910 attempt 1**, run `f-dev--django__django-11910--r1`,
  artefak `files/attempts/attempt-1.diff` (temuan bot-01, 2026-07-20). Diff attempt 1
  isinya **HANYA tiga file untracked hasil coba-coba model** — `manual_repro_app/__init__.py`,
  `manual_repro_app/migrations/__init__.py`, `manual_repro_app/models.py` — dan **nol
  perubahan** pada file kandidat `django/db/migrations/autodetector.py`. Jadi sampah
  scratch model masuk ke ekstraksi diff, sementara satu-satunya file yang boleh diedit
  justru kosong. Di run ini pre-check masih menangkapnya (1× `off-candidate-files`,
  lalu 29× `empty-diff` dari total 57 penolakan DONE), jadi celahnya tidak sampai
  meloloskan fix palsu — tapi bentuk kebocorannya persis seperti yang dijelaskan entri
  ini, dan pre-check yang menyelamatkan bekerja di himpunan yang lain lagi.
- **Diagnosa:** akar-harness murni (dua sumber kebenaran untuk satu himpunan; klasik
  "standar ganda", pelanggaran prinsip #6 di katalog cerita).
- **Usulan lever:** satukan himpunan file jadi satu sumber kebenaran yang dipakai pagar edit
  maupun ekstraksi diff.
- **Status:** BELUM DITERAPKAN.
- **Prioritas:** sedang (murah, mekanis, dan menutup celah integritas).

## LV-04 — Prompt LOCALIZE jadi kriteria-outcome

- **Asal-usul:** django-13660, akar #1a. Sesi bot-05 2026-07-20, commit `795415f`.
  Bukti hasil: `l-dev--django__django-13660--r4`, `f-dev--django__django-13660--r3`.
- **Gejala:** slot `expectation` di candidates.md berisi *resep cara/edit* alih-alih
  *kriteria hasil*, diduga meng-anchor FIX ke `exec(cmd, {})`.
- **Diagnosa:** hipotesis "LOCALIZE menyesatkan FIX" — terbukti MELESET. Akar sebenarnya
  ada di pemahaman model soal semantik namespace `exec`, yang muncul independen di kedua fase.
- **Usulan lever (sebagaimana diterapkan):** geser slot `expectation` dan `what` ke
  kriteria-outcome + Quality rule #6 "State the target, not the edit". Enforcement
  **prompt-only** — keputusan sadar, karena gate mekanis tidak bisa menilai free text.
- **Status:** DITERAPKAN (`795415f`) → **GUGUR** sebagai penyelesai 13660.
  Hasil: L r4 qualified, FIX r3 flip, tetapi checker L2 resolved=FALSE dengan p2p_failed
  identik — Gemma menulis `exec(cmd, {})` lagi. Candidate 1 r4 bahkan tetap menempelkan
  resep lama sebagai contoh di dalam slot kriteria yang baru. Prompt kriteria hanya
  MEMBUNGKUS resep salah, tidak membuangnya.
  Tidak di-revert: higiene kriteria-vs-resep tetap dianggap sah, walau tak cukup sendiri.
- **Prioritas:** —(selesai divonis). Nilainya kini sebagai bukti: konfirmasi ke-sekian bahwa
  aturan pasif tidak menggigit, dan pendorong LV-01 naik ke prioritas utama.

---

## Entri baru — autopsi REPRODUCE django-13660 (bot-01, 2026-07-20)

**Korpus:** `artifacts/r-dev/r-dev--django__django-13660--r1`, `--r2`, `--r3`.
Model `google/gemma-4-31B-it`, driver `run_reproduce_gemma-v0`, kontrak varian `slim`,
budget 60 pesan (tak pernah habis).

**Angka mentah:** 39 turn model total (r1=11, r2=13, r3=15); **10 event `retry`**
(r1=2, r2=4, r3=4). Verdict: r1 pass, r2 pass (run qualified terakhir), r3 `wrong-logic`.

**Konteks yang membingungkan Papan 103:** 13660 memang mudah *sebagai bug*. Gemma memahami
bug-nya dengan benar dan cepat di ketiga run — r2 t9 menyebut persis
`shell.py` baris 87 `exec(options['command'])` tanpa globals → `NameError`. Base-side FAIL
disaksikan bersih dan reproducible di ketiga run. **Nyaris seluruh kesulitan yang teramati
bukan tentang bug-nya, melainkan tentang mekanika harness.** Kelas-kelasnya di bawah.

## LV-05 — Aturan `app-runtime` tidak boleh membatalkan bukti yang sudah disaksikan

- **Asal-usul:** REPRODUCE django-13660, **3 dari 3 run** (r1 console baris 495, r2 baris
  471, r3 baris 519). Artefak kunci: `files/repro-first-fail.py` di ketiga run dir.
- **Gejala — kelas "judge menolak repro yang sudah terbukti, atas dasar aturan gaya"
  (3× berulang, 100% run):**
  Di setiap run, Gemma lebih dulu menulis repro `subprocess` sederhana yang **BEKERJA**:
  exec-pair run1 + run2 dua-duanya mencetak traceback `NameError: name 'django' is not
  defined` di `shell.py:87` diikuti `REPRO_STATUS: FAIL`, exit 0. Driver bahkan menyimpannya
  sebagai checkpoint known-good (`[driver] checkpoint saved: files/repro-first-fail.py`).
  Judge lalu menolak DONE dengan alasan yang identik di tiga run, mengutip
  `rule:app-runtime`: *"the script uses `subprocess.Popen` instead of
  `from pipe_runtime import App`"*. Tercatat sebagai `retry` /
  `done-deferred: judge review found issues`. Seluruh churn di kelas LV-06 dan LV-07
  terjadi SETELAH penolakan ini.
- **Bukti paling telak:** komentar Gemma sendiri di checkpoint r1, sebelum ditolak:
  > `# We don't have a "ready_token" because this is a short-lived command,`
  > `# not a long-running server. ... App is designed for long-running processes.`
  > `# For a CLI tool, subprocess.run is more appropriate.`

  Model mendiagnosis ketidakcocokan abstraksi dengan tepat, lalu **dipaksa harness
  meninggalkan analisis yang benar itu.**
- **Bukti penguat (case kedua, independen, kategori aturan BERBEDA) — django-13230**, run
  `r-dev--django__django-13230--r1` (temuan bot-01, 2026-07-20). Bukti:
  `console.log` baris 962 (`[driver] checkpoint saved: files/repro-first-fail.py`),
  baris 1026 (temuan `[judge]`), baris 1030 (`[driver] DONE deferred: judge review found
  issues`), baris 1651 (`DONE at turn 20 (last attempt 7)`); `events.jsonl` event retry
  ke-5 (`done-deferred: independent review found issues`).
  Pola persis sama: di turn 13 model sudah punya repro yang **BEKERJA** dan sudah
  disaksikan driver — exec-pair 2 run segar, dua-duanya `Item comments: None` +
  `REPRO_STATUS: FAIL`, exit 0 — dan driver menyimpannya sebagai checkpoint known-good.
  Judge lalu menahan DONE. Bedanya dengan 13660: **aturan yang dikutip bukan kategori
  mekanika**, melainkan *"Follow the user's action path"* — kategori correctness. Judge
  beralasan script *"calls `get_feed` directly, which does not exercise the `add_item`
  method where the missing argument is located"*.
- **Klaim judge itu terbukti salah secara faktual**, dan buktinya ada di gold patch case ini:
  header hunk `cases/gold/django__django-13230/gold.patch` berbunyi
  `@@ -212,6 +212,7 @@ def get_feed(self, obj, request):` — yaitu `feed.add_item(...)`
  memang dipanggil **dari dalam `get_feed`**. Memanggil `get_feed` adalah cara paling
  langsung untuk melatih call site yang rusak; judge menyatakan sebaliknya tanpa membuka kode.
- **Ongkos yang bisa dihitung:** 7 dari 20 turn (35% run) habis SETELAH penolakan ini —
  t15 mencoba `MyFeed.as_view()` → `AttributeError: type object 'MyFeed' has no attribute
  'as_view'` (kelas `Feed` syndication memang bukan CBV standar); t17 mencoba
  `from django.utils.feedgenerator import FeedGenerator` → `ImportError: cannot import name
  'FeedGenerator'`; t18–t19 membaca ulang `feedgenerator.py` untuk menemukan nama sebenarnya
  (`SyndicationFeed`). **2 dari 7 retry event di run ini adalah anak langsung penolakan judge.**
  Repro final malah memasang `except TypeError:` yang di dalamnya memanggil
  `view.get_feed(None, request)` — persis yang dilarang judge — jadi objeksinya tidak hanya
  salah, tetapi juga tidak efektif. Dan hasil akhirnya **lebih longgar** dari checkpoint yang
  ditolak (lihat bukti penguat di LV-01).
- **Implikasi untuk desain lever (b) — penting, ini memperluas cakupan entri ini:** filter
  yang diusulkan di (b) menyaring temuan judge berkategori `mechanics`. Di 13230 kategorinya
  `correctness`, jadi **(b) sebagaimana ditulis tidak akan menyelamatkan run ini.** Yang
  ternyata dibutuhkan adalah kewajiban bukti, bukan kategori aturan — lihat LV-13.
- **Diagnosa — akar-harness, hampir murni.** Dua cacat terpisah:
  1. **Pemicu aturan terlalu luas.** Teks di `harness/stages/reproduce_prompt.md`
     (`rule:app-runtime`) berbunyi *"When your scenario runs an application as a child
     process"*, padahal seluruh badan aturannya mengandaikan proses berumur panjang
     (`ready_token`, `wait_ready()` tiap reload). `django shell -c` adalah perintah
     one-shot; ia tidak punya ready line dan memang harus mati. Aturan yang lahir untuk
     membunuh race baseline `runserver` ikut menjerat perintah sekali-jalan.
  2. **Presedensi vonis terbalik.** Judge (yang dirancang *advisory*) secara efektif
     membatalkan bukti mekanis yang sudah dikumpulkan gate (exec-pair 2 run segar, dua-duanya
     FAIL). Melanggar prinsip "vonis milik harness, judge advisory" dan prinsip
     "standar tunggal kebenaran".
- **Usulan lever (mekanis, dua bagian — bagian b adalah yang mengikat):**
  - (a) **Sempitkan pemicu aturan** di `reproduce_prompt.md`: `rule:app-runtime` berlaku
    hanya ketika skenario butuh semantik readiness/reload — yaitu aplikasi yang harus TETAP
    HIDUP melintasi sebuah trigger. Perintah one-shot dikecualikan eksplisit.
  - (b) **Pagar presedensi di driver:** judge **tidak boleh** menahan DONE atas dasar aturan
    berkategori *mekanika* (`app-runtime`, `robust-scaffold`) ketika driver SUDAH menyaksikan
    exec-pair hijau (2 run segar, dua-duanya `REPRO_STATUS: FAIL`). Implementasi konkret:
    beri tiap rule sebuah kategori di rule catalog (`correctness` vs `mechanics`); driver
    menyaring temuan judge berkategori `mechanics` menjadi catatan non-blocking begitu bukti
    pair tersedia. Bukti mengalahkan gaya, secara mekanis.
- **Status:** BELUM DITERAPKAN.
- **Prioritas:** **UTAMA.** Ini pemicu hulu: menutupnya membuat LV-06 dan LV-07 kemungkinan
  besar tidak pernah terpicu di case-case berbentuk CLI one-shot. Berulang 3/3 run —
  deterministik, bukan noise. Biayanya murah dan tidak menyentuh penalaran model sama sekali.

## LV-06 — `App` butuh mode one-shot + output yang bisa dibaca program

- **Asal-usul:** REPRODUCE django-13660, r2 dan r3 (`events.jsonl`, `detail.why`).
- **Gejala — dua kelas bertetangga, total **7 penolakan**:**
  - **Kelas "API `App` dihalusinasi" — 5×.** Semua adalah upaya membaca kembali output anak
    proses, atau membawa kebiasaan `subprocess`:
    - r2: `TypeError: __init__() got an unexpected keyword argument 'text'`
    - r2: `AttributeError: 'App' object has no attribute 'stdout'`
    - r3: `TypeError: __init__() got an unexpected keyword argument 'capture_output'`
    - r3: `AttributeError: 'App' object has no attribute 'process'`
    - r3: `AttributeError: 'App' object has no attribute 'logs'`
  - **Kelas "`start()` gagal ready pada perintah one-shot" — 2×** (r1, r2):
    `RuntimeError: pipe_runtime: app failed to become ready (application exited before
    printing the ready line)`.
- **Jalan memutar yang akhirnya dipakai:** di r1 dan r2 Gemma lolos hanya dengan menyuruh
  proses anak **menulis hasilnya ke file di disk**, lalu membaca file itu setelah
  `app.stop()`. Repro qualified r2 (`files/repro.py`) berbentuk demikian: satu perintah
  one-shot dibungkus `try/except` yang menulis traceback ke `result.txt`, ditambah
  `print('READY')` artifisial di baris pertama semata-mata agar `App.start()` mau lewat.
  Ini bukan kecerdikan model, ini gejala: model membangun kanal keluaran sendiri karena
  API tidak menyediakannya.
- **Diagnosa — akar-harness dominan, dengan komponen model kecil.**
  - *Akar-harness:* `App` memodelkan satu bentuk dunia saja (server berumur panjang dengan
    ready line). (i) `start()` **wajib** ready_token dan melempar RuntimeError kalau proses
    mati duluan — padahal untuk 13660 "proses mati dengan traceback" ADALAH gejala yang
    diuji; (ii) output anak hanya di-*echo* ke stdout, sementara `self._lines` privat —
    **tidak ada satu pun jalan yang didukung untuk membaca output dari dalam script.**
    Kelima nama yang dihalusinasi Gemma (`.stdout`, `.process`, `.logs`, `text=`,
    `capture_output=`) adalah peta yang rapi dari lubang API ini.
  - *Akar-model:* menebak nama API alih-alih membaca modul yang jelas-jelas ada dan terbaca
    di sandbox. Nyata, tapi sekunder — dan persis kelas yang di proyek ini sudah tiga kali
    dijawab dengan menutup celah API, bukan dengan menegur model.
- **Usulan lever (perluasan API `pipe_runtime`, menutup kelas by construction):**
  - `App.run_once(timeout=...)` — spawn, tunggu proses selesai, kembalikan exit code.
    Tanpa `ready_token`, tanpa `RuntimeError` saat proses mati (mati adalah hasil yang sah).
  - `app.output()` / `app.lines()` — kembalikan salinan read-only baris yang sudah tertangkap.
  - `app.exit_code` — properti eksplisit.
  Konsekuensinya `.stdout`/`.logs`/`.process` tidak perlu ditebak lagi, `result.txt`
  tidak perlu ada, dan `print('READY')` palsu hilang.
- **Status:** BELUM DITERAPKAN.
- **Prioritas:** tinggi. Ini iterasi ke-4 dari pola yang sudah terbukti di fase REPRODUCE
  (cursor `850b345`, auto-settle `a7add92`, grace window `0c3ecca`): tiap salah-pakai API
  diperlakukan sebagai celah API yang ditutup permanen sehingga permukaan kesalahan
  menyempit. 5 event halusinasi = 5 titik bukti yang menyebut nama API yang hilang.
- **Ketergantungan:** kalau LV-05 dipasang duluan, lever ini jadi lebih jarang terpicu —
  tapi tetap layak, karena begitu ada case yang MEMANG butuh `App` sekaligus butuh membaca
  output, lubangnya kembali menganga.

## LV-07 — Kunci PASS observable ke token kanonik

- **Asal-usul:** REPRODUCE django-13660 **r3** — satu-satunya run yang divonis
  `wrong-logic`. Bukti: `console.log` baris 934 (`PASS_OBSERVABLE: 2.`) dan baris 988
  (`[driver] DONE at turn 15 ...; pass observable verified: '2.'`);
  `events.jsonl` event exit; `files/repro.py`.
- **Gejala (1×, tapi ini justru satu-satunya kegagalan vonis di seluruh korpus):**
  r3 mula-mula mendeklarasikan `PASS_OBSERVABLE: REPRO_STATUS: PASS` (baris 463), lalu
  belakangan menggantinya jadi `PASS_OBSERVABLE: 2.` — potongan string versi Django.
  Driver menerima. Repro r3 memutuskan PASS lewat `app.wait_for("2.", timeout=2)`, dengan
  cabang `else` yang **default-nya mencetak FAIL**. Di dunia gold, `f()` berhasil dan
  mencetak versi, tapi string versinya tidak memuat literal `2.`; tidak ada cabang yang
  cocok → jatuh ke `else` → FAIL. Flip test: base FAIL, patched FAIL →
  *"predicate not satisfied by the gold fix — likely gold-unsatisfiable predicate"*.
- **Diagnosa — campuran, dan penting untuk tidak dibulatkan ke satu sisi.**
  - *Akar-model:* memilih substring versi yang rapuh sebagai bukti sisi-PASS, plus
    `else` yang default ke FAIL sehingga sisi PASS praktis tak pernah bisa menang.
    Ini kecerobohan penalaran predikat yang asli.
  - *Akar-harness (yang bisa dilever):* (i) driver menerima observable PASS sembarang,
    padahal kontrak sendiri mendefinisikan `REPRO_STATUS: PASS` sebagai token kanonik dan
    r1/r2 memakainya; (ii) sisi-PASS memang tak pernah dieksekusi sebelum DONE, jadi
    tidak ada gesekan mekanis apa pun yang menyentuh cabang itu.
  - *Amplifier dari LV-06:* r3 terpaksa memakai `wait_for` atas baris mentah aplikasi —
    dan komentar di `files/repro.py` r3 menyebutnya eksplisit
    (*"Since we don't have access to app.logs, we use wait_for"*). Kalau output bisa dibaca,
    predikat versi-string yang rapuh itu kemungkinan besar tak pernah ditulis.
- **Usulan lever:** driver **menolak** deklarasi `PASS_OBSERVABLE` yang bukan token kanonik
  `REPRO_STATUS: PASS` ketika script memang mencetak baris `REPRO_STATUS` sendiri (dan itu
  wajib menurut kontrak). Murah, mekanis, satu titik cek, dan menyeragamkan standar
  kebenaran antara mid-loop, pre-check, dan gate.
- **Status:** BELUM DITERAPKAN.
- **Prioritas:** sedang.
- **Catatan jujur soal ketegangan desain:** mekanisme `PASS_OBSERVABLE` aslinya lahir untuk
  keperluan lain — verifikasi anti-konfabulasi lewat grep ke source container (`d7e93b6`).
  Mengunci token ke `REPRO_STATUS: PASS` berpotensi melumpuhkan fungsi itu. Jadi lever ini
  **butuh spec kecil dulu**, bukan langsung dipatch: perlu dipastikan dua peran (token vonis
  vs observable yang digrep) memang bisa dipisah. Prior art yang relevan dan mungkin lebih
  tepat sasaran: **self-flip-check** (validasi predikat murni base-world) yang sudah disebut
  di katalog cerita vignette (e). Kalau harus memilih satu, self-flip-check menyerang akarnya
  lebih langsung. Bukti dari korpus ini **belum cukup** untuk memutuskan mana yang lebih baik
  — 1 kejadian, 1 run.

## LV-08 — Reinstatement checkpoint known-good setelah churn

- **Asal-usul:** REPRODUCE django-13660, r1/r2/r3 (`files/repro-first-fail.py` + jejak
  turn di `console.log`).
- **Gejala:** driver menyimpan checkpoint known-good di ketiga run, lalu **tidak pernah
  memakainya lagi**. Setelah penolakan judge (LV-05), model mengembara 4–7 turn menjauh dari
  script yang sudah terbukti; r3 tidak pernah kembali dan berakhir `wrong-logic`.
  Checkpoint berfungsi sebagai artefak forensik, bukan sebagai jaring pengaman.
- **Bukti penguat (case kedua, independen) — django-13230**, run
  `r-dev--django__django-13230--r1` (temuan bot-01, 2026-07-20). `console.log` baris 962
  menyimpan `files/repro-first-fail.py`; setelah penolakan judge di baris 1030, model menulis
  ulang `repro.py` **3×** (baris 1162, 1341, 1570) dan berkelana **7 turn** (t14–t20) tanpa
  sekali pun kembali ke script yang sudah terbukti. Checkpoint tidak pernah disodorkan lagi.
  Perbedaan dengan 13660: di sini run-nya akhirnya lolos (verdict `pass`), jadi kerugiannya
  bukan kegagalan vonis melainkan **7 turn hangus plus yardstick akhir yang lebih longgar
  daripada checkpoint yang dibuang** (LV-01). Ambang N=4 yang diusulkan entri ini akan
  memicu tepat di t17–t18, saat model masih menebak-nebak nama simbol `feedgenerator`.
- **Diagnosa:** akar-harness (mekanisme ada tapi pasif). Berbeda dari `next-step nudge`
  (`4541654`) yang menangani loop degeneratif — di sini modelnya justru produktif, hanya
  saja produktif ke arah yang salah.
- **Usulan lever:** ketika sebuah checkpoint known-good sudah tersimpan dan sejak itu model
  melewati N turn (mis. N=4) tanpa mencapai DONE, driver **menyodorkan kembali isi checkpoint
  itu** ke konteks sebagai basis kerja, disertai alasan penolakan yang masih berlaku.
  Mekanis, tidak menambah aturan, dan memakai artefak yang sudah dikumpulkan.
- **Status:** BELUM DITERAPKAN.
- **Prioritas:** rendah — sengaja. Ini lever **orde kedua**: di korpus ini, seluruh churn
  yang akan diselamatkannya justru disebabkan LV-05. Perbaiki hulunya dulu; kalau setelah
  LV-05 terpasang masih ada run yang mengembara dari checkpoint, barulah lever ini punya
  bukti mandiri. Dicatat sekarang supaya tidak hilang.

---

## Catatan penutup autopsi 13660 (bot-01, 2026-07-20)

Kesimpulan yang paling layak dibawa ke keputusan berikutnya:

1. **Papan 103 tidak keliru.** 13660 memang mudah untuk Gemma. Pemahaman bug-nya benar di
   ketiga run, sejak turn-turn awal, dan base-side FAIL disaksikan bersih dan reproducible.
2. **Dari 10 penolakan di fase REPRODUCE, 10-nya berkaitan dengan mekanika harness**, bukan
   dengan bug Django: 3 penolakan gaya oleh judge, 5 halusinasi API `App`, 2 kegagalan
   `start()` pada perintah one-shot. Tidak ada satu pun `retry` yang sebabnya "salah paham
   bug".
3. **Satu-satunya kegagalan vonis (r3 `wrong-logic`) memang punya komponen akar-model** —
   predikat sisi-PASS yang rapuh — tetapi lahir di dalam ruang gerak sempit yang dibuat
   oleh dua kelas di atas.
4. **Ironi yang perlu dicatat:** `pipe_runtime` adalah lever tersukses proyek ini (membunuh
   kelas race baseline yang kambuh 8×). Di 13660 ia justru menjadi sumber kesulitan utama,
   karena aturan pemakaiannya dipicu terlalu luas. Lever yang benar untuk satu bentuk dunia
   bisa jadi beban di bentuk dunia lain — argumen kuat agar pemicu tiap aturan diberi
   ruang lingkup sesempit buktinya, bukan seluas kalimatnya.

---

## Entri baru — komparasi kontras django-11910 (meledak) vs django-11099 (mulus)
## (bot-01, 2026-07-20)

**Korpus:**
`artifacts/f-dev/f-dev--django__django-11910--r1` (gagal, verdict `no-flip`),
repro beku dari `artifacts/r-dev/r-dev--django__django-11910--r3`;
dibandingkan dengan `artifacts/r-dev|l-dev|f-dev--django__django-11099--r1`
(full green, `resolved=true`, F2P 3/3, P2P 19/19).

**Angka mentah komparasi:**

- 11910 FIX: `console.log` **17.927 baris**, `events.jsonl` 707 baris, 2 attempt ×
  **40 turn = 80 turn**, `winner_attempt=null`, `fix.diff` tidak pernah ditulis,
  **57 penolakan DONE**, `pass_l1=false`.
- 11099 seluruh pipeline: REPRODUCE **5 turn** (console 177 baris, **0 event retry**),
  LOCALIZE **2 turn**, FIX **4 turn / 1 attempt / result=win** (console 394 baris).
  Total ± **11 turn** untuk tiga fase, tanpa satu pun rerun.
- Rasio kasar: 80 turn tanpa hasil vs 11 turn hijau — sekitar **7×**, dan itu pun
  membandingkan tiga fase 11099 dengan satu fase 11910.

**Beda struktural yang paling menonjol — bentuk repro:**

- 11099 `files/repro.py`: **murni in-process.** `from django.contrib.auth.validators
  import ASCIIUsernameValidator, UnicodeUsernameValidator`, panggil validator atas 4
  string, tangkap `ValidationError`, cetak status. Nol subprocess, nol tmpdir, nol
  `pipe_runtime`, nol file I/O, nol proses anak. Satu-satunya state eksternal adalah
  isi modul yang sedang diperbaiki — yaitu persis variabel yang ingin diukur.
- 11910 `files/repro.py`: **orkestrasi environment penuh.** `tempfile.TemporaryDirectory`
  + `os.chdir` + bikin app Django sintetis (`repro_app/`, `migrations/`, `models.py`,
  `manage.py` yang ditulis sebagai string) + **dua kali** `makemigrations` lewat
  `pipe_runtime.App` (yang kedua dibungkus `/bin/sh -c "echo 'y' | ..."` untuk menjawab
  prompt interaktif rename) + baca kembali file migrasi ke-2 dari disk + cocokkan
  substring `to_field='field_wrong'`. Rantai ketergantungan: cwd, tmpdir, sqlite,
  `pipe_runtime`, semantik `App.start()/stop()`, timing prompt interaktif, urutan
  `sorted()` nama file migrasi.

Bentuk kedua punya belasan titik gagal yang **tidak satu pun berhubungan dengan bug
Django-nya**. Ketika satu titik itu putus, repro tidak berteriak — ia diam-diam
mencetak PASS (lihat LV-10).

**Catatan kejujuran soal hipotesis "in-process lebih deterministik":** bukti di korpus
ini **mendukung arah itu tapi belum cukup untuk membuktikannya**, dan ada confounder
besar. Kegagalan 11910 sebagian besar bisa dijelaskan oleh satu cacat tunggal yang
sangat spesifik (LV-09: dependency repro tidak ikut dikirim ke container FIX) —
bukan oleh "orkestrasi itu sendiri". Kalau LV-09 ditutup, belum tentu 11910 tetap
meledak. Yang **bisa** diklaim dengan bukti: repro berorkestrasi punya permukaan
kegagalan yang jauh lebih lebar, dan cacat LV-09 hanya bisa menggigit repro yang
punya dependency runtime — repro in-process 11099 kebal terhadapnya secara struktural.
n=1 vs n=1; jangan dijadikan aturan sebelum ada case ketiga.

## LV-09 — Container kerja FIX tidak menerima dependency yang dibutuhkan repro beku

- **Asal-usul:** django-11910. Bukti utama:
  `artifacts/f-dev/f-dev--django__django-11910--r1/console.log` (588 kejadian
  `ModuleNotFoundError: No module named 'pipe_runtime'` — 56 di attempt 1, **532 di
  attempt 2**), dibandingkan dengan
  `artifacts/r-dev/r-dev--django__django-11910--r3/gate_runs.json`.
  Kode: `harness/stages/run_fix_gemma.py` baris 231–232 vs
  `harness/stages/run_reproduce_gemma.py` baris 286 dan
  `harness/stages/repro_sandbox_runner.py` baris 35–36.
- **Gejala:** repro beku 11910 diawali `from pipe_runtime import App`. Di **dunia gate**
  (fase REPRODUCE) modul itu ada, dan `gate_runs.json` r3 menunjukkan dua run segar yang
  dua-duanya bersih: 2 migrasi terbentuk, prompt rename terjawab, `REPRO_STATUS: FAIL`,
  exit 0 — flip base FAIL → gold PASS lolos. Di **dunia kerja FIX**, baris pertama repro
  langsung mati dengan `ModuleNotFoundError`. Attempt 2 tidak pernah berhasil menjalankan
  repro **sekali pun** sepanjang 40 turn; error yang sama berulang 532×. Attempt 1 lolos
  dari loop itu hanya karena model **menulis `pipe_runtime.py` tiruannya sendiri**
  (`[driver] wrote /testbed/.pipe/pipe_runtime.py (950 chars)`, console baris 2555;
  percobaan pertamanya bahkan menyertakan literal `EOF` di badan file →
  `NameError: name 'EOF' is not defined`).
- **Akar mekanis, sudah terverifikasi di kode:** `run_reproduce_gemma.py` mengirim DUA
  file ke container (`repro.py` + `pipe_runtime.py`), dan `repro_sandbox_runner.py`
  menyalin `pipe_runtime.py` ke sandbox gate. `run_fix_gemma.py` hanya menulis **satu**
  file: `docker_write_file(container, "/testbed/.pipe/repro.py", inputs.repro_py)`.
  Tidak ada `pipe_runtime.py`. Kontrak yang dibekukan adalah *script*-nya saja, bukan
  *lingkungan* tempat script itu terbukti bekerja.
- **Bukti penguat (sisi kontrol — case yang BERSIH dari `pipe_runtime` dan mulus) —
  django-13230**, run `r-dev--django__django-13230--r1` + `f-dev--django__django-13230--r1`
  (temuan bot-01, 2026-07-20). Angka keras:
  - `r-dev/.../files/repro.py`: **0 kemunculan** string `pipe_runtime`. Repro-nya in-process
    murni (`settings.configure` + `django.setup()` + `call_command('migrate')` + panggilan
    langsung ke objek Feed). Driver tetap mengirim `pipe_runtime.py` ke container REPRODUCE
    (`console.log` baris 2: `[driver] pipe_runtime.py shipped to container and files/`), tapi
    repro tidak memakainya.
  - `f-dev/.../console.log`: **0 kemunculan** `No module named 'pipe_runtime'`, **0**
    `ModuleNotFoundError` apa pun, **0** kemunculan string `pipe_runtime`.
  - Hasil fase FIX: **3 turn, 1 attempt, `win`**, 1 penolakan DONE (dan itu pun sekadar
    `done-rejected: Not done yet: run python /testbed/.pipe/repro.py ... first`), berujung
    `resolved=true`.
  Bandingkan dengan 11910: 588 `ModuleNotFoundError`, 80 turn, `winner_attempt=null`.
  **Korelasi lintas tiga case kini konsisten:** repro yang mengimpor `pipe_runtime` → fase FIX
  meledak (11910); repro tanpa `pipe_runtime` → fase FIX selesai dalam 3–4 turn (13230, 11099).
  Ini bukti korelasional, bukan eksperimen terkontrol — tapi arahnya searah dengan akar mekanis
  yang sudah **diverifikasi di kode** (`run_fix_gemma.py` baris 231–232), sehingga fungsinya
  menguatkan, bukan menggantikan, bukti kode itu.
- **Diagnosa — akar-harness murni, dan ini bukan non-determinisme.** Penting untuk tidak
  salah label: hipotesis kerja sebelumnya adalah "script yang sama berperilaku beda
  antara dunia gate dan dunia FIX, jadi tidak deterministik lintas dunia". Bukti
  menunjukkan sebab yang jauh lebih membosankan dan jauh lebih bisa diperbaiki: **dunia
  FIX kekurangan satu file**. Kedua dunia sepenuhnya deterministik; yang berbeda adalah
  isinya. Turunannya: perilaku "acak" yang teramati di attempt 1 (`found 0`, lalu
  `found 1`, sesekali `FAIL`) adalah efek dari `pipe_runtime` **tiruan buatan model**
  yang semantik `start()`/`stop()`-nya berbeda dari yang asli — bukan flakiness Django.
- **Ironi lintas-lever:** `rule:app-runtime` di prompt REPRODUCE (lihat LV-05) secara
  aktif **mendorong** model memakai `pipe_runtime`, bahkan menolak repro `subprocess`
  yang sudah terbukti. Setiap repro yang tunduk pada aturan itu lalu menjadi
  **tidak-bisa-dijalankan di fase FIX**. Dua lever yang masing-masing masuk akal
  bertabrakan di sambungan antar-fase.
- **Usulan lever (mekanis, murah, satu titik):** apa pun yang dikirim harness ke
  container REPRODUCE sebagai penopang repro **wajib dikirim juga ke tiap container
  kerja FIX**, dari satu daftar sumber-kebenaran tunggal (bukan dua pemanggilan
  `docker_write_file` terpisah yang kebetulan beda isi). Bentuk konkret: satu fungsi
  `provision_pipe_dir(container)` dipakai oleh REPRODUCE, sandbox gate, dan FIX.
  Ini persis pola "satukan himpunan jadi satu sumber kebenaran" yang sudah ada di LV-03,
  tapi atas objek yang berbeda (isi `/testbed/.pipe`, bukan himpunan file yang boleh
  diedit) — karena itu dicatat sebagai lever tersendiri, bukan bukti penguat LV-03.
- **Status:** BELUM DITERAPKAN.
- **Prioritas:** **UTAMA.** Ini penjelasan tunggal terbesar untuk 80 turn yang hangus.
  Perbaikannya beberapa baris, tidak menyentuh penalaran model sama sekali, dan
  menutup kelas untuk **semua** case yang repro-nya memakai `App` — yaitu kelas yang
  justru dibesarkan oleh `rule:app-runtime`.

## LV-10 — Repro beku wajib divalidasi ulang mencetak FAIL di container kerja pristine

- **Asal-usul:** django-11910, `f-dev--django__django-11910--r1/console.log`
  (baris 2367–2368, 2541–2542, 2665–2666, 3119–3120, dst.) dan repro beku
  `r-dev--django__django-11910--r3/files/repro.py` baris 72–74 + 86–91.
- **Gejala (angka):** pada repo yang **belum difix sama sekali**, repro mencetak:
  `Expected at least 2 migrations, found 0` diikuti `REPRO_STATUS: PASS`. Sepanjang run,
  `REPRO_STATUS: PASS` muncul **30×** dan `REPRO_STATUS: FAIL` hanya **5×** — dan
  mayoritas PASS itu berasal dari cabang "environment-ku tidak jalan", bukan dari
  "bug-nya hilang". Model menyadarinya sendiri dan menulis di console:
  *"So 'found 1' is a false positive."* — lalu tetap tidak punya cara keluar, karena
  satu-satunya sinyal vonis yang tersedia baginya sudah rusak.
- **Mekanisme kerusakan:** repro punya cabang `if len(migration_files) < 2: ... return
  False`, dan pemanggilnya menerjemahkan `False` menjadi `REPRO_STATUS: PASS`. Jadi
  **kegagalan environment tidak bisa dibedakan dari perbaikan yang benar**. Kombinasinya
  dengan LV-09 mematikan: dependency hilang → environment gagal → repro bilang PASS →
  model diberi tahu bahwa ia sudah menang padahal belum menyentuh kode. Yang menahan
  false-flip di sini hanya kebetulan: pre-check `empty-diff` menolak DONE 29× karena
  file kandidat memang kosong. Kalau model kebetulan sudah menulis apa pun ke file
  kandidat, run ini akan lolos gate flip dengan fix sembarang.
- **Diagnosa — akar-harness murni, dua cacat terpisah yang keduanya bisa dilever:**
  1. **Tidak ada pre-flight.** `run_fix_gemma.py` menulis `repro.py` ke container lalu
     langsung menyerahkan giliran ke model. Tidak pernah dicek bahwa yardstick-nya
     masih hidup di dunia ini. Padahal invarian yang dibutuhkan sepele dan bisa diuji
     dalam satu detik: di container pristine (belum ada edit), repro **harus** mencetak
     `REPRO_STATUS: FAIL`.
  2. **Cabang error jatuh ke PASS.** Kontrak repro hanya mengenal dua keluaran, jadi
     setiap kondisi "aku tidak bisa mengamati apa-apa" terpaksa dibulatkan ke salah
     satunya — dan model membulatkannya ke arah yang paling berbahaya. Ini bukan
     kesalahan model semata: **kontraknya memang tidak menyediakan kata untuk
     "tidak tahu"**.
- **Usulan lever (dua bagian, keduanya mekanis):**
  - (a) **Gerbang pre-flight FIX.** Sebelum pesan pertama ke model, driver menjalankan
    repro beku di container kerja yang masih pristine. Kalau keluarannya bukan
    `REPRO_STATUS: FAIL` (termasuk kalau PASS, kalau exit non-nol, atau kalau tidak
    ada baris `REPRO_STATUS` sama sekali), **abort attempt itu** dengan verdict khusus
    — usul nama `repro-not-armed` — dan jangan bakar satu turn pun. Verdict terpisah
    penting supaya kegagalan infrastruktur tidak tersamar sebagai `no-flip`, yang di
    papan skor terbaca seolah model gagal memperbaiki bug. Di 11910 seluruh 80 turn
    akan dipotong di detik pertama, dengan diagnosis yang benar.
  - (b) **Tambah keluaran ketiga di kontrak repro:** `REPRO_STATUS: ERROR` (atau
    `INCONCLUSIVE`) untuk setiap jalur di mana script tidak berhasil mengamati sistem.
    Gate REPRODUCE menolak repro yang cabang error/short-circuit-nya jatuh ke PASS —
    ini bisa dicek sebagian secara statis (mis. `return False`/`else` yang dicapai dari
    blok `except` atau dari guard "prasyarat tidak terpenuhi"), dan sepenuhnya secara
    dinamis dengan menjalankan repro di container **tanpa** repo (sabotase sengaja):
    kalau ia mencetak PASS di sana, repro-nya cacat menurut konstruksi.
  Bagian (a) adalah yang mengikat dan bisa dipasang hari ini. Bagian (b) menutup akarnya
  tapi butuh perubahan kontrak, jadi biayanya lebih tinggi.
- **Hubungan dengan lever lain:** (a) juga menangkap LV-09 tanpa tahu apa-apa soal
  `pipe_runtime` — ia adalah **detektor generik** untuk seluruh kelas "yardstick mati di
  dunia kerja", sementara LV-09 adalah perbaikan penyebab spesifik yang sudah diketahui.
  Keduanya layak: LV-09 mencegah, LV-10 menjaring sisanya. Kalau hanya boleh satu,
  pasang **LV-10(a)** — cakupannya lebih luas dan biayanya sebanding.
- **Status:** BELUM DITERAPKAN.
- **Prioritas:** **UTAMA** untuk bagian (a); sedang untuk bagian (b).

## LV-11 — Repro beku harus benar-benar beku (read-only) selama fase FIX

- **Asal-usul:** django-11910, `f-dev--django__django-11910--r1/console.log`
  baris 2555 (`[driver] wrote /testbed/.pipe/pipe_runtime.py`), baris 3184 dan 3322
  (`sed -i "s/print(f\"Expected at least 2 migrations...` atas
  `/testbed/.pipe/repro.py`).
- **Gejala:** premis fase FIX adalah *"repro.py dibekukan dan jadi SATU-SATUNYA
  yardstick"*. Kenyataannya model bisa, dan memang, **mengubah yardstick-nya sendiri**:
  ia menjalankan `sed -i` atas `/testbed/.pipe/repro.py` (2×) dan menulis modul
  penopangnya sendiri ke `/testbed/.pipe/`. Driver tidak punya pagar apa pun di
  `/testbed/.pipe`: `docker_write_file` menerima path apa saja dari aksi `file`, dan
  aksi `bash` dieksekusi mentah.
- **Diagnosa — akar-harness murni.** "Beku" di sini adalah **konvensi, bukan mekanisme**
  — persis pola yang berulang kali gagal di proyek ini (lihat LV-08: checkpoint yang
  ada tapi pasif; LV-04: aturan yang hanya dituliskan). Perlu dicatat adil: di run ini
  motif model **bukan** kecurangan, melainkan usaha memperbaiki yardstick yang memang
  rusak karena LV-09. Tetap saja, begitu yardstick bisa diedit oleh pihak yang sedang
  diuji, verdict flip kehilangan arti.
- **Usulan lever:** setelah provisioning, `chmod 0444` seluruh isi `/testbed/.pipe` dan
  jalankan proses model sebagai user non-root; driver menolak aksi `file` yang path-nya
  di bawah `/testbed/.pipe`; dan sebagai jaring terakhir, driver menyimpan hash isi
  `/testbed/.pipe/repro.py` saat provisioning lalu **memverifikasi ulang hash itu tepat
  sebelum menerima DONE** — hash berubah = attempt gugur. Bagian hash paling murah dan
  paling sulit dielakkan.
- **Status:** BELUM DITERAPKAN.
- **Prioritas:** tinggi. Bukan karena sudah terbukti merusak vonis (di 11910 tidak
  sampai, karena `empty-diff` menahan DONE), tapi karena ia **melubangi integritas
  gate** — sekali sebuah run lolos flip dengan repro yang sudah diedit sendiri, seluruh
  papan skor kehilangan makna dan kita tidak akan tahu dari artefak mana pun. Biayanya
  beberapa baris.
- **Ketergantungan:** pasang **bersama** LV-09 dan LV-10, jangan sendirian. Menutup akses
  edit tanpa memperbaiki dependency yang hilang berarti model terkurung dengan yardstick
  yang mati dan tanpa jalan keluar — hasilnya tetap 40 turn hangus, hanya lebih senyap.

## LV-12 — Preferensikan repro in-process; orkestrasi environment hanya bila perlu

- **Asal-usul:** komparasi django-11910 vs django-11099 (rincian angka di blok komparasi
  di atas). Bukti: `r-dev--django__django-11099--r1/files/repro.py` (in-process murni,
  5 turn, 0 retry) vs `r-dev--django__django-11910--r3/files/repro.py` (tmpdir + app
  sintetis + 2× `makemigrations` + prompt interaktif + baca file hasil).
- **Gejala:** repro berorkestrasi menyeret belasan titik gagal yang tidak ada
  hubungannya dengan bug yang diuji (cwd, tmpdir, sqlite, `pipe_runtime`, timing prompt
  rename, urutan `sorted()` nama migrasi). Di 11910 satu titik saja yang putus
  (`pipe_runtime` absen) sudah cukup untuk membuat yardstick diam-diam bohong. Repro
  in-process 11099 kebal terhadap kelas itu secara struktural: satu-satunya state yang
  disentuhnya adalah modul yang sedang diperbaiki.
- **Bukti penguat (case ketiga — kelas ANTARA, dan ia menuntut taksonomi yang lebih halus) —
  django-13230**, `r-dev--django__django-13230--r1/files/repro.py` (temuan bot-01,
  2026-07-20). Repro ini **in-process** (nol subprocess, nol `pipe_runtime`, nol tmpdir, nol
  file I/O) tetapi **tidak sesederhana 11099**: ia harus mem-bootstrap framework yang sedang
  diuji — `settings.configure(...)` dengan `DATABASES`/`ALLOWED_HOSTS`/`INSTALLED_APPS`/
  `SITE_ID`, `django.setup()`, `call_command('migrate', run_syncdb=True)`, lalu
  `Site.objects.create(...)`. Ongkosnya nyata dan terukur: **2 dari 7 retry** di fase REPRODUCE
  murni boilerplate bootstrap (`events.jsonl` retry ke-2 `DisallowedHost: Invalid HTTP_HOST
  header: 'testserver'` → t6 menambah `ALLOWED_HOSTS`; retry ke-3 `ImproperlyConfigured:
  settings.DATABASES is improperly configured` → t7 menambah sqlite in-memory).
  **Yang penting untuk lever ini:** biaya bootstrap itu dibayar **sekali di fase REPRODUCE**
  dan **nol di fase FIX** (3 turn, mulus) — berbeda total dari orkestrasi 11910 yang biayanya
  terbayar berulang setiap kali repro dijalankan di dunia lain. Jadi metadata "kelas repro"
  yang diusulkan entri ini sebaiknya **tiga nilai, bukan dua**: (i) in-process murni,
  (ii) in-process + bootstrap framework, (iii) orkestrasi proses/environment. Perbedaan
  yang menggigit ada di batas (ii)/(iii), bukan (i)/(ii).
- **Diagnosa — campuran, dan bukti belum tuntas.**
  - *Akar-harness:* kontrak REPRODUCE tidak menyatakan preferensi bentuk apa pun, dan
    `rule:app-runtime` bahkan mendorong ke arah sebaliknya (LV-05).
  - *Confounder yang harus diakui:* kegagalan 11910 **sudah cukup dijelaskan** oleh
    LV-09 sendiri. Kita **tidak punya bukti** bahwa orkestrasi per se yang merusak;
    yang terbukti hanyalah bahwa orkestrasi memperlebar permukaan kegagalan sehingga
    cacat harness punya tempat menggigit. n=1 vs n=1.
  - Perlu juga jujur: sebagian case memang **tidak bisa** diuji in-process. 11910 adalah
    bug pada *hasil generate migrasi* — sulit dibuktikan tanpa menjalankan autodetector
    atas sepasang model state. Lever ini karenanya tidak boleh berbentuk larangan.
- **Usulan lever:** jadikan preferensi bentuk sebagai **urutan yang diperiksa gate, bukan
  larangan**. Konkretnya: gate REPRODUCE mencatat "kelas repro" (in-process / subprocess
  / orkestrasi penuh) sebagai metadata di `verdict.json`, sehingga kelas ini bisa
  dikorelasikan dengan hasil L2 lintas case. Baru **setelah** ada 5–10 case, putuskan
  apakah layak menekan bentuknya. Menambah kalimat "tulislah repro in-process" ke prompt
  sekarang adalah persis jenis lever yang katalog ini sudah tiga kali buktikan tidak
  menggigit (LV-04, dan L#1–L#3 di LOCALIZE).
- **Status:** BELUM DITERAPKAN — dan **sengaja belum diusulkan sebagai perubahan
  perilaku**, baru sebagai instrumentasi.
- **Prioritas:** rendah untuk lever-nya, **sedang untuk instrumentasinya**. Alasan: ini
  satu-satunya item di batch ini yang buktinya belum cukup. Mengubah bentuk repro
  berdasarkan n=1 adalah cara termahal untuk belajar (aturan main #6). Mencatat kelasnya
  murah dan membuat keputusan berikutnya berbasis data.

---

## Catatan penutup komparasi 11910 vs 11099 (bot-01, 2026-07-20)

1. **Kegagalan 11910 hampir seluruhnya akar-harness, bukan akar-model.** Localization-nya
   benar (kandidat attempt 1 `autodetector.py` **adalah** file gold), dan analisis awal
   model atas `to_field_rename_key` di baris 928–929 tepat sasaran. Yang membunuh run
   ini adalah yardstick yang tidak bisa dijalankan di dunia tempat ia dipakai (LV-09)
   dan tidak pernah diperiksa apakah masih hidup (LV-10). Dari 80 turn, mayoritas mutlak
   habis untuk melawan `ModuleNotFoundError` — 588 kejadian.
2. **Komponen akar-model tetap ada dan tidak boleh disapu bersih:** script sisip-blok
   attempt 2 yang merusak `related.py` 23× adalah kecerobohan asli (LV-02), dan cabang
   `< 2 migrations → PASS` di repro adalah pilihan desain predikat yang buruk oleh model
   (walau kontrak yang tidak menyediakan "ERROR" ikut bersalah — LV-10b).
3. **Hijau 11099 tidak boleh dibaca sebagai validasi gate.** Repro-nya tidak menguji
   anchor depan sama sekali; fix minimal maupun fix Gemma yang lebih ketat sama-sama
   lolos. Ruang fix yang sempit (satu regex, satu file) yang menyelamatkan, bukan
   yardstick-nya. Dicatat sebagai bukti penguat di LV-01.
4. **Pola yang mulai berulang di seluruh katalog ini:** mekanisme yang ADA tapi PASIF —
   checkpoint yang tak pernah dipakai (LV-08), aturan "beku" tanpa pagar (LV-11),
   kontrak repro tanpa keluaran "tidak tahu" (LV-10b), dua sumber kebenaran untuk satu
   himpunan (LV-03, LV-09). Semua akar-harness, semua murah, dan semuanya berbentuk
   sama: **jadikan invarian yang sudah kita percayai itu diperiksa oleh mesin.**
5. **Urutan pasang yang disarankan:** LV-10(a) dulu (detektor generik, langsung memberi
   diagnosis benar untuk seluruh kelas), lalu LV-09 (perbaikan penyebab), lalu LV-11
   (pagar integritas), lalu LV-02. LV-12 cukup diinstrumentasi dan ditunggu datanya.

---

## Entri baru — autopsi django-13230: full green yang mahal di REPRODUCE
## (bot-01, 2026-07-20)

**Korpus:** `artifacts/r-dev/r-dev--django__django-13230--r1`,
`artifacts/l-dev/l-dev--django__django-13230--r1`,
`artifacts/f-dev/f-dev--django__django-13230--r1`.
Gold: `cases/gold/django__django-13230/gold.patch`.

**Hasil (terverifikasi ulang dari artefak, bukan dari laporan):** FULL GREEN.
`f-dev/.../swebench_eval.json` → `resolved=true`, `patch_successfully_applied=true`,
F2P 1/1 (`test_rss2_feed (syndication_tests.tests.SyndicationFeedTest)`), P2P 23/23,
`f2p_failed=[]`, `p2p_failed=[]`, `rerun=1`. Ketiga fase `pass_l1=true`.
Patch model setara semantik dengan gold: baris yang disisipkan identik
(`comments=self._get_dynamic_attr('item_comments', item),`), hanya beda posisi sisip
(model menaruhnya sesudah `item_copyright`, gold sesudah `author_link`).

**Angka biaya per fase:**

- REPRODUCE: **20 turn model, 7 attempt internal**, 7 event `retry`, 1 ronde self-check
  yang diinjeksi driver (tidak tercatat sebagai retry), `console.log` 1.655 baris.
- LOCALIZE: **2 turn**, 0 retry, `console.log` 327 baris. `qualified=true`.
- FIX: **3 turn, 1 attempt**, 1 penolakan DONE, `result=win`, `console.log` 602 baris.

**Perbandingan yang memicu autopsi ini:** django-11099 juga full green tapi REPRODUCE-nya
hanya **5 turn / 1 attempt / 0 retry**. Jadi: 20 vs 5. Pertanyaannya, ke mana 15 turn itu pergi?

**Pembagian ongkos 20 turn (dari `console.log`, per turn, dibaca satu per satu):**

- **t1–t5 (5 turn) — orientasi + signature `get_feed`.** Model membaca `views.py` dan
  `feedgenerator.py`, lalu salah urutan argumen (`get_feed(self, obj, request)` vs
  `(self, request, obj)`) → retry ke-1. Ini kerja normal, akar-model, wajar.
- **t6–t7 (2 turn) — boilerplate bootstrap Django.** `DisallowedHost` → tambah
  `ALLOWED_HOSTS`; `ImproperlyConfigured: settings.DATABASES` → tambah sqlite in-memory.
  Retry ke-2 dan ke-3. Ini satu-satunya bagian yang **murah ditutup harness**, dan buktinya
  masih tipis (lihat Catatan penutup #3).
- **t8–t12 (5 turn) — semantik `_get_dynamic_attr` / signature `items()`.** Retry ke-4
  (`TypeError: items() missing 1 required positional argument: 'request'`), lalu 4 turn
  membaca ulang sumber sampai paham bahwa `_get_dynamic_attr` memanggil `attr()` tanpa
  argumen. **Akar-model murni**, dan ini kerja intelektual yang sah: case ini memang punya
  permukaan API yang lebih kaya daripada 11099 (yang cuma mengimpor dua validator dan
  memanggilnya atas empat string).
- **t13 — repro BEKERJA.** exec-pair 2 run segar, dua-duanya `REPRO_STATUS: FAIL`, exit 0.
  Driver menyimpan checkpoint known-good.
- **t14–t20 (7 turn, 35% run) — detour yang dipaksa judge.** Rinciannya di LV-05 (bukti
  penguat 13230) dan LV-13. Menghasilkan retry ke-6 (`as_view` tidak ada) dan ke-7
  (`ImportError: FeedGenerator`).

**Kelas kegagalan REPRODUCE (7 retry, dikelompokkan dari `detail.why` di `events.jsonl`):**

- Kelas **"salah paham API kode yang sedang diuji"** — **3×**: `get_feed()` kurang argumen
  `request`; `items()` kurang argumen `request`; `MyFeed` tidak punya `as_view`.
  Akar-model. Tidak ada lever mekanis yang jelas — sumbernya terbaca di sandbox dan model
  memang akhirnya membacanya.
- Kelas **"boilerplate bootstrap framework"** — **2×**: `DisallowedHost`,
  `settings.DATABASES improperly configured`. Akar-harness lemah (kandidat lever, bukti tipis).
- Kelas **"nama simbol dihalusinasi"** — **1×**: `ImportError: cannot import name
  'FeedGenerator'` (yang benar `SyndicationFeed`). Akar-model, tapi **dipicu** oleh detour judge.
- Kelas **"judge menolak repro yang sudah terbukti"** — **1×**. Akar-harness. Ini yang
  paling mahal per kejadiannya: 1 event retry, 7 turn.

**Kesimpulan biaya, jujur:** dari 15 turn selisih terhadap 11099, kira-kira **10 turn adalah
kerja model yang sah** (case ini secara intrinsik lebih berat: butuh bootstrap Django penuh
dan pemahaman `_get_dynamic_attr`), **7 turn adalah mekanisme yang SUDAH tercatat** (LV-05),
dan **2 turn boilerplate** adalah satu-satunya sisa yang belum tercatat. Tidak ada mekanisme
kegagalan besar yang baru ditemukan di sini — dan itu sendiri temuan: katalog yang ada sudah
menjelaskan bagian harness dari kemahalan run ini. **Tidak ada satu pun retry yang sebabnya
"salah paham bug-nya"** — persis seperti di 13660.

## LV-13 — Klaim faktual tentang kode wajib diverifikasi mesin ke kode (citation check)

- **Asal-usul:** django-13230, dua titik independen dalam satu run.
  - (A) **Judge di fase REPRODUCE.** `r-dev--django__django-13230--r1/console.log`
    baris 1026 + 1030; `events.jsonl` retry ke-5.
  - (B) **Slot `evidence`/`lines` di fase LOCALIZE.**
    `l-dev--django__django-13230--r1/files/localize.md` dan `files/candidates.md`;
    `gold_eval.json` (`pointed_lines: [145, 165]`, `line_overlap: false`,
    `file_match: true`, `criterion: shortlist-v2`, `qualified: true`).
- **Gejala (A) — klaim judge yang salah, diterima driver sebagai penahan DONE:**
  judge menulis bahwa script *"calls `get_feed` directly, which does not exercise the
  `add_item` method where the missing argument is located"*. Gold patch case ini membantahnya
  langsung — header hunk-nya `@@ -212,6 +212,7 @@ def get_feed(self, obj, request):`, jadi
  `feed.add_item(...)` memang berada **di dalam** `get_feed`. Driver tidak pernah meminta judge
  menunjukkan bukti, dan tidak punya cara untuk menolak klaim yang salah. Ongkos: 7 turn,
  2 retry, dan repro final yang lebih longgar daripada checkpoint yang dibuang (LV-01).
- **Gejala (B) — `evidence` LOCALIZE mengarang lokasi dan nama simbol, tetap qualified:**
  `localize.md` menyatakan *"In `django/contrib/syndication/views.py`, the `add_item` method
  (lines 145-165) builds `item_dict` using `self.item_title`, ..."*. Di file itu **tidak ada
  method bernama `add_item`** — `add_item` adalah method `SyndicationFeed` di
  `django/utils/feedgenerator.py`, dan call site yang rusak ada di `get_feed` sekitar baris
  212. Jadi model menyebut nama method yang salah di file yang benar, dan rentang baris yang
  meleset ~50 baris. Menariknya **kesimpulannya tetap benar** (views.py gagal meneruskan
  `comments`; `feedgenerator.add_item` sudah menerimanya), dan FIX menyelesaikannya dalam
  3 turn. Harness merekam ketidakcocokan itu (`line_overlap: false`) tetapi **tidak ada satu
  konsumen pun** untuk sinyal itu: `shortlist-v2` meluluskan atas dasar file saja.
- **Diagnosa — akar-harness murni, satu mekanisme di dua tempat.** Di kedua titik, harness
  menerima **prosa tentang kode** sebagai masukan yang menentukan (menahan DONE; mengisi slot
  yang diteruskan ke fase berikutnya) **tanpa pernah mencocokkannya dengan kode**. Padahal
  pencocokannya sepele dan deterministik: nama simbol yang dikutip bisa di-grep di file yang
  dikutip; rentang baris yang dikutip bisa dicek memuat simbol itu. Ini pola yang sudah
  berulang di katalog ini — invarian yang kita percayai tapi tidak diperiksa mesin
  (LV-03, LV-08, LV-09, LV-10, LV-11).
  Komponen akar-model ada tapi sekunder dan tidak seragam: di (A) yang salah adalah **judge**
  (model yang sama, peran berbeda), di (B) yang salah adalah **model LOCALIZE**. Yang seragam
  justru sisi harness-nya.
- **Usulan lever (mekanis, dua bagian, keduanya di titik vonis):**
  - (a) **Judge blocking wajib bersitasi.** Temuan judge hanya boleh menahan DONE kalau ia
    menyertakan sitasi yang bisa diverifikasi mesin — minimal `file:symbol` atau
    `file:baris` — dan driver **memverifikasi sitasi itu di container** (grep simbol di file
    yang dikutip) sebelum meneruskannya. Sitasi yang tidak terverifikasi → temuan didegradasi
    jadi catatan non-blocking. Ini melengkapi LV-05(b): LV-05(b) menyaring berdasarkan
    *kategori aturan* dan karena itu tidak akan menangkap 13230 (aturannya berkategori
    correctness); LV-13(a) menyaring berdasarkan *ada-tidaknya bukti*, dan menangkap keduanya.
    Kalau harus memilih satu, **(a) lebih luas**.
  - (b) **Verifikasi sitasi LOCALIZE.** Gate LOCALIZE memeriksa bahwa nama simbol yang disebut
    di slot `evidence` benar-benar ada di file yang ditunjuk, dan bahwa rentang `lines` memuat
    simbol itu. Ketidakcocokan **tidak perlu menggugurkan** kandidat — cukup dicatat di
    `verdict.json` sebagai flag `citation_mismatch` dan (opsional) dikirim balik ke model
    sebagai satu ronde koreksi. Alasan tidak menggugurkan ada di Catatan penutup #2.
- **Status:** BELUM DITERAPKAN.
- **Prioritas:** **tinggi untuk (a)**, sedang untuk (b). Alasan (a): ia menutup jalur yang
  di dua case berturut-turut (13660 lewat LV-05, 13230 lewat entri ini) terbukti jadi
  penyebab churn terbesar di fase REPRODUCE, dan ia mengikat di titik vonis tanpa menyentuh
  penalaran model. Alasan (b) lebih rendah: di 13230 sitasi yang salah **tidak merugikan
  hasil sama sekali**, jadi nilainya saat ini instrumentasi, bukan perbaikan.
- **Catatan kejujuran:** ini n=1 untuk masing-masing titik (A) dan (B). Yang membuatnya
  layak dicatat sekarang bukan frekuensinya, melainkan (i) klaim (A) bisa dibuktikan salah
  secara definitif dari gold patch — bukan soal selera, dan (ii) mekanismenya identik di dua
  peran yang berbeda dalam satu run, yang membuat generalisasinya lebih kuat daripada
  hitungan kejadiannya.

---

## Catatan penutup autopsi 13230 (bot-01, 2026-07-20)

1. **Full green TIDAK berarti pipeline-nya sehat.** Run ini `resolved=true` dengan patch
   setara gold, tapi 35% turn REPRODUCE-nya habis melawan objeksi judge yang salah, dan
   yardstick yang akhirnya dibekukan lebih longgar daripada yang sudah terbukti di turn 13.
   Papan skor tidak merekam satu pun dari itu. Ini alasan ketiga (setelah 11099 dan 14017)
   untuk tidak membaca kolom hijau sebagai validasi gate.
2. **`line_overlap: false` di LOCALIZE — dinilai, dan vonisnya: BUKAN cacat kriteria.**
   Pertanyaannya "apakah `shortlist-v2` terlalu longgar?" Jawaban dari bukti case ini:
   **tidak.** Fase FIX menerima **file** kandidat, bukan rentang baris — container FIX
   dibuka dengan `candidate django/contrib/syndication/views.py` dan model bebas membaca
   seluruh file. Rentang 145–165 yang meleset ~50 baris tidak pernah dipakai sebagai
   pembatas apa pun, dan FIX menemukan call site yang benar di 3 turn. Memperketat kriteria
   jadi wajib-`line_overlap` akan **menggugurkan run yang berhasil** — persis jenis lever
   yang menyerang akar yang salah (aturan main #6). Yang sahih dari observasi ini bukan
   pengetatan kriteria, melainkan bahwa `line_overlap` adalah **detektor konfabulasi gratis
   yang tidak ada konsumennya** — dan itulah yang dicatat sebagai LV-13(b), sebagai
   instrumentasi, bukan sebagai gate.
3. **Kandidat lever yang SENGAJA TIDAK dijadikan entri: helper bootstrap framework.**
   2 dari 7 retry (dan 2 turn) habis untuk `ALLOWED_HOSTS` dan `DATABASES` — boilerplate yang
   tidak ada hubungannya dengan bug. Bentuk mekanisnya jelas dan mengikuti pola yang sudah
   sukses di proyek ini (kirim modul penopang ke container, seperti `pipe_runtime.py`):
   sediakan `repro_support.django_setup(**overrides)` yang sudah benar sejak awal. **Tetapi
   buktinya terlalu tipis untuk sebuah entri: 2 kejadian, 1 case, 2 turn** — dan ongkosnya
   hanya dibayar sekali di REPRODUCE, nol di FIX. Dicatat di sini supaya tidak hilang;
   naikkan jadi entri kalau case Django berikutnya menunjukkan kelas yang sama. Peringatan
   yang menyertainya: modul penopang apa pun yang ditambahkan **wajib** ikut aturan LV-09
   (dikirim juga ke container FIX dari satu sumber kebenaran), kalau tidak ia akan
   melahirkan ulang persis kelas kegagalan 11910.
4. **Repro monkeypatch vs repro yang memeriksa keluaran akhir — dinilai, dan vonisnya:
   masih LV-01, bukan mekanisme baru.** Repro 13230 berhenti di boundary internal
   (`SyndicationFeed.add_item`) alih-alih memeriksa XML yang diperiksa `test_rss2_feed`.
   Tanda tangannya sama dengan 13660/14017/11099: predikat proksi yang lebih sempit daripada
   kontrak yang dilanggar, sehingga hijau tidak informatif. Dicatat sebagai bukti penguat
   ketiga di LV-01, bukan entri sendiri (aturan main #4). Yang **baru** dan layak dicatat
   adalah **sebabnya**: bentuk longgar itu bukan pilihan awal model — checkpoint di turn 13
   memeriksa `feed_gen.items[0]['comments']` tanpa monkeypatch dan tanpa `except TypeError`
   lebar. Longgarnya yardstick di sini adalah **produk sampingan dari objeksi judge**
   (LV-05/LV-13) yang mendorong model ke jalur dispatch view. Artinya LV-01 dan LV-05 tidak
   berdiri sendiri-sendiri: kualitas yardstick ikut ditentukan oleh siapa yang boleh
   membatalkan bukti di fase REPRODUCE.
5. **LV-09 kini punya tiga titik korelasi yang searah**, dan case ini adalah kontrolnya:
   repro bersih dari `pipe_runtime` → 0 `ModuleNotFoundError` di FIX → 3 turn menang.
   Bukan pengganti bukti kode (`run_fix_gemma.py:231–232`), tapi ia menutup kemungkinan
   bahwa 11910 gagal karena sebab lain yang kebetulan bersamaan.
