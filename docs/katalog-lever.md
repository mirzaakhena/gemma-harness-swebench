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
