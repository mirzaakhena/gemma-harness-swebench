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
- **Bukti penguat (case keempat — yardstick paling longgar di korpus sejauh ini) —
  django-12915**, run `r-dev--django__django-12915--r2/files/repro.py` (temuan bot-01,
  2026-07-20). Repro ini qualified (`verdict.json` pass, flip base FAIL → gold PASS) dan
  dipakai fase FIX sampai full green, tetapi **tidak memuat satu pun assert atas nilai**:
  - `async def send(message): pass` — **seluruh pesan ASGI dibuang**. Padahal justru di
    pesan-pesan itulah jawabannya berada: F2P resmi `test_static_file_response` memeriksa
    `response_start['status'] == 200`, empat header (`Content-Length`, `Content-Type`,
    `Content-Disposition`, `Last-Modified`), dan `response_body['body'] == test_file_contents`.
    Repro membuang semuanya lalu mencetak `Request handled successfully`.
  - Vonis PASS-nya murni **"tidak ada exception yang lolos"** (`try: await handler(...)` →
    `return "PASS"`). Jadi predikatnya bukan "sempit", melainkan **kosong** di sisi PASS —
    satu langkah lebih jauh dari 13660/14017/11099/13230, yang setidaknya masih memeriksa
    *sesuatu*.
  - **Cabang `except Http404` gold tidak pernah dieksekusi.** Script membuat `test.txt`
    lebih dulu sehingga `self.serve()` selalu sukses; jalur 404 tidak pernah disentuh —
    padahal gold punya **dua** baris dan SWE-bench punya F2P khusus untuknya
    (`test_get_async_response_not_found`). Repro menutupi 1 dari 2 baris gold.
  - **Kontrol positifnya mati:** `mock_app` didefinisikan sebagai inner application tetapi
    tidak pernah dieksekusi (`ASGIStaticFilesHandler` menangani `/static/...` sendiri dan
    tidak pernah mendelegasikan ke `self.application`). Sama seperti catatan kontrol positif
    di bukti 13230.
  Tanda tangan sama: predikat proksi lebih sempit daripada kontrak yang dilanggar, dan
  hijau karenanya tidak informatif. **Konsekuensi baru yang layak dicatat:** di case ini
  yardstick yang kosong itu tetap menghasilkan `resolved=true` — jadi repro longgar bukan
  hanya "tidak bisa membedakan"; ia juga tidak memberi tekanan apa pun ke arah patch yang
  setara gold (lihat LV-14).
- **Bukti penguat (case kelima — predikatnya yang paling mudah dipalsukan sejauh ini) —
  django-12286**, `r-dev--django__django-12286--r1/files/repro.py` (temuan bot-01,
  2026-07-20). Repro ini qualified, dibekukan, dipakai fase FIX, dan berujung full green —
  tetapi seluruh vonisnya bertumpu pada **satu substring**:
  `if "translation.E004" in output: FAIL` dengan `else: print("REPRO_STATUS: PASS")`,
  atas stdout `manage.py check`. Tiga konsekuensi yang bisa dibaca langsung dari script:
  - **Setiap mode kegagalan jadi PASS.** Wrapper anak (`run_check.py`, ditulis ke disk oleh
    repro) membungkus subprocess-nya dengan `except Exception as e:
    print(f"Execution failed: {e}")` lalu tetap mencetak `CHECK_FINISHED`. Di pemanggil,
    output yang tidak memuat `translation.E004` — entah karena bug-nya hilang, entah karena
    settings salah, entah karena Django gagal boot, entah karena `manage.py` tidak ketemu —
    semuanya jatuh ke cabang `else` dan mencetak `REPRO_STATUS: PASS`. Ini tanda tangan
    LV-10(b) yang muncul lagi, kali ini di repro yang benar-benar dipakai sampai vonis.
  - **Tidak ada kontrol positif.** Tidak ada satu pun cabang yang memaksa script membuktikan
    bahwa ia betul-betul mengeksekusi `check` dan betul-betul mampu **melihat** E004 kalau ada.
  - **Fix `return []` tanpa syarat akan LOLOS repro ini.** Predikatnya adalah "E004 tidak
    muncul", bukan "E004 muncul untuk kode yang memang tak didukung dan hilang untuk yang
    didukung" — repro ini tidak punya sisi negatif sama sekali.
  Tanda tangan sama dengan 12915 (predikat sisi-PASS praktis kosong). Yang **beda dan layak
  dicatat**: di 12915 kekosongan itu berbentuk *tidak ada assert sama sekali*; di sini
  berbentuk **satu assert yang polaritasnya searah dengan semua mode kegagalan**. Bentuk
  kedua lebih sulit terlihat, karena script-nya *tampak* punya assert — jadi kalau kelak
  ada pemeriksaan otomatis atas kualitas repro (LV-01/LV-10b), "ada assert" bukan predikat
  yang cukup; yang harus dicek adalah **apakah cabang gagal-mengamati bisa mendarat di PASS**.
- **Bukti penguat (case keenam — predikat substring dua-arah tanpa kontrol positif, di run
  FULL GREEN) — django-11039**, `r-dev--django__django-11039--r2/files/repro.py`
  (temuan bot-01, 2026-07-20). Repro qualified, dipakai fase FIX, berujung `resolved=true`
  (F2P 1/1, P2P 88/88). Seluruh vonisnya adalah satu baris:
  `if "BEGIN" in stdout and "COMMIT" in stdout: FAIL else: PASS` atas stdout child process
  `manage.py sqlmigrate`. Konsekuensi yang bisa dibaca langsung dari script:
  - **Sisi PASS didefinisikan oleh KETIADAAN.** stdout kosong karena perintah mati, settings
    salah, backend sintetis gagal di-import, atau `manage.py` tidak ketemu — semuanya tidak
    memuat `BEGIN`, jadi semuanya mencetak `REPRO_STATUS: PASS`. Tanda tangan identik dengan
    12286, hanya substringnya beda.
  - **Nol kontrol positif.** Tidak ada satu pun cabang yang memaksa script membuktikan bahwa
    ia betul-betul menjalankan `sqlmigrate` dan betul-betul mampu **melihat** `BEGIN` kalau
    ada. Bandingkan dengan `r-dev--django__django-11422--r44` dan `--13768--r4`, yang
    keduanya memasang kontrol positif eksplisit dan menolak mencetak status kalau kontrolnya
    gagal — jadi bentuk yang benar **ada di korpus ini** dan bukan hal eksotis.
  - **`self.output_transaction = False` tanpa syarat akan LOLOS repro ini.** Predikatnya
    "BEGIN tidak muncul", bukan "BEGIN muncul untuk backend yang mendukung DDL transaksional
    dan hilang untuk yang tidak" — sekali lagi tidak ada sisi negatif.
  Nilai tambahnya di atas 12286: di sini kelonggaran itu **tidak lahir dari kemalasan model**.
  Checkpoint r2 (`files/repro-first-fail.py`) memakai koneksi Django **sungguhan** dan
  mematikan `connection.features.can_rollback_ddl` langsung — bentuk yang jauh lebih tepat
  sasaran — lalu dibuang setelah penolakan judge (LV-05/LV-08). Ini kejadian **kedua** setelah
  13230 di mana yardstick yang dibekukan terbukti lebih longgar daripada yang sudah disaksikan
  driver, dan sebabnya sama.
- **Bukti penguat (case ketujuh — repro yang predikatnya "tidak ada exception", di run yang
  `resolved=true`) — django-13658**, `r-dev--django__django-13658--r1/files/repro.py`
  (temuan bot-01, 2026-07-20). Repro qualified (2 turn di LOCALIZE, dipakai FIX sampai
  `resolved=true`). Seluruh vonisnya:
  `try: execute_from_command_line(['my_prog','help']); return True` / `except Exception: return
  False`, lalu `True → REPRO_STATUS: PASS`. Konsekuensi yang bisa dibaca langsung:
  - **Predikatnya crash-vs-tidak-crash**, bukan nilai. Bug 13658 adalah *program name dihitung
    dari argv pemanggil, bukan dari `sys.argv`* — yaitu klaim tentang **string**. Repro tidak
    pernah memeriksa string apa pun. Tanda tangan sama dengan 12915 (sisi PASS kosong) dan
    11039/12286 (predikat satu-arah), jadi ini kemunculan ketujuh.
  - **Ironi yang layak dicatat:** repro ini memakai `custom_argv = ['my_prog', 'help']` —
    yaitu ia **sudah membangun persis skenario yang membedakan** gold dari fix salah, lalu
    membuang hasilnya tanpa diperiksa. Selisih yang tersedia gratis di variabel `out`-nya
    (gold → top-level parser `prog='my_prog'`; patch model → `'django-admin'`) tidak pernah
    ditanyakan. Kontrol positif juga nol (K4).
  - Bedanya dengan enam bukti sebelumnya, dan ini yang membuatnya penting: di 13660/14017
    repro longgar meloloskan fix salah yang **lalu ketahuan di L2**. Di 13658 **L2 juga tidak
    melihatnya** (rincian di autopsi 13658 di bawah dan di LV-14) — jadi ini case pertama di
    korpus di mana kelonggaran repro dan plafon alat ukur resmi **bertepatan pada run yang sama**.
- **Bukti penguat (case kedelapan — sisi kontrol, dan ia mempertegas K4 sebagai kriteria
  yang paling kurang terwakili) — django-11179**, `r-dev--django__django-11179--r1/files/repro.py`
  (temuan bot-01, 2026-07-20). Repro ini termasuk yang **lebih baik** dari rata-rata korpus:
  in-process murni, nol `pipe_runtime`, dan vonisnya adalah **perbandingan nilai** (`obj.pk is
  None`) — bukan substring, bukan "tidak melempar exception". Jadi ia **bukan** K1 dan **bukan**
  K5. Tetapi ia tetap **K4**, dan lubangnya bisa dinyatakan dengan satu contoh:
  > fix yang menyetel `instance.pk = None` lalu `return 0, {}` **tanpa pernah menjalankan
  > `delete_batch`** akan tetap LOLOS repro ini — karena repro tidak pernah memverifikasi
  > bahwa barisnya benar-benar terhapus dari DB (`SimpleModel.objects.count()` tidak pernah
  > dipanggil sesudah `delete()`).
  Nilainya untuk entri ini: K4 menggigit **terlepas dari** kualitas predikatnya. Repro boleh
  memeriksa nilai dengan benar dan tetap tidak punya cara membuktikan bahwa yang ia ukur
  memang dihasilkan oleh mekanisme yang seharusnya. Ini menguatkan arah yang sudah dicatat di
  Konsekuensi tabel frekuensi butir 2 (kontrol positif sebagai isi konkret pertama LV-01),
  dan menambah satu bentuk kontrol yang murah dan tidak membocorkan gold sama sekali:
  **assert atas efek samping yang seharusnya menyertai perbaikan**, bukan hanya atas gejalanya.
- **Bukti penguat (case kesembilan — dan yang PERTAMA memisahkan dua sumbu kelemahan repro
  secara empiris) — django-13590**, `r-dev--django__django-13590--r1/files/repro.py` +
  `f-dev--django__django-13590--r1` (temuan bot-01, 2026-07-20). Run ini **MERAH**
  (`resolved=false`), jadi ia masuk sini bukan sebagai lulus-palsu melainkan sebagai
  **alat ukur atas alat ukur**: repro-nya disabotase enam kali dan hasilnya membelah rapi
  jadi dua kelompok yang selama ini kita perlakukan sebagai satu.
  - **Kerusakan LINGKUNGAN ditolak, 3 dari 4.** `filter()` dirusak di jalur repro →
    `REPRO_STATUS: UNKNOWN`; `SyntaxError` disuntik ke `sql/query.py` → UNKNOWN; Django
    dibuat tak bisa di-import → UNKNOWN. (Yang lolos: `create()` dirusak **di luar** jalur
    repro → PASS, dan itu memang benar — repro tidak memakai `create()`.) Sebabnya bisa
    dibaca langsung di script, baris 75–78: seluruh badan repro dibungkus
    `except Exception: traceback.print_exc(); print("REPRO_STATUS: UNKNOWN")`.
  - **Kerusakan SEMANTIK tidak ditolak, 2 dari 2.** D1 (`return [...]` — selalu paksa ke
    `list`, membuang pelestarian tipe yang justru jadi inti bug) → **PASS**. D2
    (`return value` — sub-ekspresi tidak pernah diresolusi sama sekali) → **PASS**.
    Sebabnya juga bisa dibaca langsung: baris 60 berbunyi
    `MyModel.objects.filter(value__range=my_range).exists()` dan **hasil `.exists()` dibuang**;
    vonis PASS-nya adalah "tidak ada `TypeError` yang lolos", persis kelas K5.
  - **Yang membuat ini penting untuk LV-01, dan bukan sekadar bukti kedelapan-belas:**
    13590 membuktikan bahwa **ketahanan terhadap kerusakan lingkungan tidak membeli
    ketajaman semantik sedikit pun**. Repro ini punya penjaga fallback terbaik di korpus
    dan tetap meloloskan dua patch yang merusak kontrak yang sedang diperbaiki. Sampai
    sekarang LV-01 (predikat terlalu longgar) dan LV-10b (cabang error jatuh ke PASS)
    sering dibela dengan bukti yang sama; case ini memisahkan keduanya dengan eksperimen,
    bukan dengan argumen. **Konsekuensi konkret:** uji sabotase dinamis yang diusulkan
    LV-10(b) (*"jalankan repro di container tanpa repo; kalau ia mencetak PASS, repro-nya
    cacat"*) akan **meluluskan 13590 dengan nilai sempurna** — dan 13590 tetap buta. Uji
    itu sah untuk sumbu-nya sendiri, tetapi **tidak boleh dijual sebagai uji kualitas
    repro secara umum**; kalau dipasang sendirian ia menghasilkan rasa aman yang salah.
  - **Bentuk kontrol yang akan menutup lubang ini, dan tetap gold-blind:** repro cukup
    menyisipkan satu baris yang **memakai hasilnya** — mis. `assert list(qs) == [obj]`
    setelah memasukkan satu baris yang memang masuk rentang, atau
    `assert type(resolved) is Range`. Keduanya diturunkan dari *issue text* ("named tuples
    used as arguments to `__range`"), bukan dari test resmi. D1 mati di assert kedua, D2
    mati di assert pertama.
- **Bukti penguat (case kesepuluh — yardstick terlemah yang pernah diuji di korpus, dan
  satu-satunya yang gagal SELURUH empat kelas sabotase) — django-14238**,
  `r-dev--django__django-14238--r1/files/repro.py` + `f-dev--django__django-14238--r1`
  (temuan bot-01, 2026-07-20). Run FULL GREEN (`resolved=true`, F2P 2/2, P2P 39/39,
  `file_match`+`line_overlap` true) dengan patch yang **setara gold**
  (`any(issubclass(subclass, s) for s in self._subclasses)` vs `issubclass(subclass,
  self._subclasses)`; setara karena `_subclasses` adalah tuple). Jadi sekali lagi: hijau
  yang benar, didapat **tanpa** bantuan yardstick.
  - Empat sabotase, empat PASS (rincian di `koreksi-hipotesis.md` KH-07):
    `__subclasscheck__` diganti `return True` → PASS; gold benar tapi `QuerySet.create()`
    disabotase → PASS; file repo ditinggalkan `SyntaxError` → PASS; **Django sama sekali
    tidak bisa di-import → PASS**.
  - **Mekanismenya bisa ditunjuk ke satu baris, dan ia bukan `else: PASS` semata.** Repro
    menjalankan pekerjaan sesungguhnya di **subprocess anak**, dan anak itu sudah
    mengklasifikasikan kegagalannya dengan benar — baris 57–58:
    `except Exception as e: print(f"OTHER_ERROR: {type(e).__name__}: {e}")`. Lalu pemanggil
    (baris 78–83) hanya bertanya dua hal: `expected_error in stdout` → FAIL,
    `"SUCCESS" in stdout` → PASS, **`else: PASS`**. Token `OTHER_ERROR` **tidak pernah
    ditanyakan**. Jadi informasi pembedanya **sudah diproduksi, lalu dibuang oleh
    pemanggilnya sendiri**. Ini tanda tangan yang sama dengan 12286 (wrapper anak
    `run_check.py`), tetapi kali ini anaknya sudah menamai kegagalannya dengan benar —
    yang hilang murni satu cabang `elif` di pemanggil.
  - **K1-ketat.** Ini anggota **keempat** kelas terburuk (setelah 11039, 11910, 12286), dan
    **yang pertama yang keanggotaannya dibuktikan dengan eksekusi, bukan dengan pembacaan.**
  - **Jejaknya terbaca di loop retry, dan itu bukti tambahan yang independen:** `events.jsonl`
    mencatat **6 dari 7 attempt gagal dengan kelas yang identik** —
    `repro run exited 0 without REPRO_STATUS: FAIL; last output line: REPRO_STATUS: PASS`.
    Enam kali model diberi tahu hal yang sama persis, karena desain repro-nya memang tidak
    mampu memproduksi sinyal lain. Bandingkan dengan 13590 di case yang sama sekali berbeda:
    12 attempt gagalnya tersebar di **enam kelas berbeda** (`ImproperlyConfigured`,
    `AppRegistryNotReady`, `ModuleNotFoundError` ×2 bentuk, `RuntimeError: populate() isn't
    reentrant`, `AttributeError`, dan satu `REPRO_STATUS: UNKNOWN`). **Polaritas cabang
    fallback karenanya bukan hanya soal kebenaran vonis akhir — ia menentukan berapa banyak
    informasi yang diterima loop retry di setiap putaran.** Repro yang membulatkan semuanya
    ke PASS membuat retry-nya buta, bukan cuma gate-nya.
- **Bukti penguat (case kesebelas — sisi kontrol positif, dan yang pertama di mana kontrol
  itu TERBUKTI menyala di dalam loop) — django-14382**,
  `r-dev--django__django-14382--r2/files/repro.py` (temuan bot-01, 2026-07-20). Run FULL
  GREEN (`resolved=true`, F2P 1/1, P2P 188/188). Repro ini adalah **anggota kelima** kelompok
  "punya kontrol positif" (setelah 10914, 11422 r44, 13768 r4, 14017), dan kontrolnya
  **load-bearing** dengan cara yang paling gamblang di korpus — baris 26–34:
  ia menjalankan `startapp control_app control_dir` ke direktori yang **benar-benar sudah
  dibuat**, dan kalau itu gagal ia mencetak `REPRO_STATUS: ERROR` lalu **`return`**, sehingga
  cabang vonis bug tidak pernah tercapai.
  - **Buktinya bukan pembacaan kode:** `events.jsonl` r2 mencatat satu attempt gagal dengan
    `repro run exited 0 without REPRO_STATUS: FAIL; last output line: REPRO_STATUS: ERROR` —
    yaitu kontrol itu **benar-benar menyala dan benar-benar menahan vonis**. Sampai sekarang
    klaim "kontrol positif murah dan sudah ada di korpus" bertumpu pada empat script yang
    kontrolnya tidak pernah terlihat gagal; ini yang pertama dengan rekaman eksekusinya.
  - **Sisi PASS-nya juga positif**, dan itu terpisah dari kontrolnya: `elif success:` menuntut
    `returncode == 0` yang teramati, bukan ketiadaan gejala. Jadi 14382 r2 **bukan K1**.
  - **Batas kontrol ini, supaya tidak di-overclaim:** kontrol positif 14382 membuktikan
    *`startapp` berfungsi di dunia ini*. Ia **tidak** membuktikan bahwa app yang dihasilkan
    benar. Repro tetap **K5** — vonisnya substring `"'' is not a valid app directory"` atas
    stderr plus exit code; ia tidak pernah memeriksa bahwa `bug_app/` benar-benar mendarat
    di dalam `bug_dir/`. Patch model (`target.rstrip(os.sep)`, yaitu usulan reporter) memang
    sedikit lebih sempit daripada gold (validasi setelah `abspath`): `"dir/."` dan
    `"dir/sub/.."` hanya tertangani normalisasi penuh ala gold. **Repro ini tidak akan
    membedakannya**, dan tidak ada test resmi yang membangunnya. Jadi kontrol positif
    menyerang **sumbu K4**, bukan sumbu K5 — dua-duanya masih perlu.
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
- **Bukti penguat (case ketiga — dan ini yang paling telak: A/B nyaris terkontrol di dalam
  SATU case) — django-12915**, `r-dev--django__django-12915--r1` vs `--r2`
  (temuan bot-01, 2026-07-20). Dua run, case sama, model sama (`google/gemma-4-31B-it`),
  driver sama, kontrak `slim` sama, dan **script yang dinilai judge secara struktural sama**:
  in-process, `ASGIStaticFilesHandler(mock_app)`, scope ASGI palsu, loop asyncio, tangkap
  `TypeError`. `diff r1/files/repro-first-fail.py r2/files/repro.py` hanya berbeda kosmetik
  plus tiga hal yang tak ada hubungannya dengan aturan yang dikutip (nilai `ROOT_URLCONF`,
  pembuatan `test.txt`, gaya `send_response`). Vonis judge-nya **berlawanan**:
  - r1 (`console.log` baris 567–574): *"REVIEW: ISSUES ... the script runs the handler
    in-process via `asyncio.run` instead of spawning a real ASGI server (e.g., using `daphne`
    or `uvicorn`) as a child process"* + *"Contract rule 'use the runtime module provided at
    /testbed/.pipe/pipe_runtime.py' violated"* → `done-deferred: judge review found issues`
    (`events.jsonl` retry ke-3, msg_used=10).
  - r2 (`console.log` baris 534): *"The script correctly identifies the missing
    `get_response_async` ... It follows the user's reported traceback and uses a minimal
    Django configuration to trigger the specific `TypeError`."* → lolos.
  **Ongkos dari satu panggilan judge yang berbeda itu, dalam angka:** r1 = **26 turn, 11
  attempt, 12 event retry, verdict `wrong-logic`** (`console.log` 2.119 baris); r2 = **10
  turn, 2 attempt, 1 retry, verdict `pass`** (541 baris). **8 dari 12 retry r1 (67%) lahir
  setelah penolakan judge**, dan **16 dari 26 turn (62%)** dijalani sesudahnya. Rangkaiannya
  terbaca lurus di console: t11 cari `daphne` (tidak terpasang, exit 1), t12 cari `uvicorn`
  (tidak terpasang, exit 1), t13 `pip list`, lalu model membangun server ASGI-nya sendiri
  di atas `pipe_runtime` → 4× `app failed to become ready` (LV-06) → 4× `REPRO_STATUS: ERROR`
  (LV-10) → flip gagal.
- **Yang membuat bukti ini beda kualitasnya dari 13660/13230:** di dua case itu judge menolak
  di **semua** run, jadi masih bisa dibaca sebagai "aturannya memang menjerat bentuk ini".
  Di 12915 aturannya menjerat **sekali dan tidak di run berikutnya atas script yang sama** —
  jadi yang terukur bukan cuma aturan yang terlalu luas, melainkan **non-determinisme judge
  atas masukan yang praktis identik**, dan selisih hasilnya adalah selisih antara gagal
  dan lolos. Presedensi vonis terbalik (cacat #2 di diagnosa) karenanya bukan risiko
  teoretis: satu lemparan koin menentukan verdict fase.
- **Catatan penting untuk desain (b) — ini kebalikan dari catatan 13230:** aturan yang
  dikutip di 12915 adalah `app-runtime` + `pipe_runtime`, dua-duanya berkategori
  **`mechanics`**, dan exec-pair hijau **sudah** disaksikan driver sebelum judge bicara
  (2 run segar, dua-duanya `Caught expected bug: 'NoneType' object is not callable` +
  `REPRO_STATUS: FAIL`, exit 0; checkpoint tersimpan di `console.log` baris 539). Jadi
  **(b) sebagaimana ditulis akan menyelamatkan run ini persis seperti yang dirancang.**
  Di 13230 (b) tidak menggigit karena kategorinya `correctness`. Kesimpulan gabungan:
  (b) berguna dan sudah punya satu case tempat ia tepat sasaran, tetapi cakupannya memang
  parsial — LV-13(a) tetap yang lebih luas.
- **Bukti penguat (case keempat — dan yang pertama di mana rantai sebabnya bisa ditelusuri
  utuh sampai ke fase FIX) — django-12286**, run `r-dev--django__django-12286--r1`
  (temuan bot-01, 2026-07-20). Bukti: `console.log` baris 705
  (`[driver] checkpoint saved: files/repro-first-fail.py`), baris 693–704
  (`[exec-fresh]` hijau), baris 762–773 (exec-pair 2 run segar, dua-duanya
  `translation.E004` + `REPRO_STATUS: FAIL`, exit 0), baris 774–780 (temuan `[judge]`),
  baris 781 (`[driver] DONE deferred: judge review found issues`); `events.jsonl` retry ke-8.
  Pola dan **kategori aturannya** identik dengan 13660/12915: judge mengutip *"when the
  behavior depends on how the program is launched, your script spawns that launch as a real
  child process"* dan *"use the runtime module provided at /testbed/.pipe/pipe_runtime.py"* —
  dua-duanya `mechanics` — atas script in-process yang **bukti mekanisnya sudah lengkap
  sebelum judge bicara**. Jadi **LV-05(b) sebagaimana tertulis akan menyelamatkan run ini**;
  case kedua setelah 12915 di mana (b) tepat sasaran.
  **Ongkos dalam angka:** t11–t19 = **9 dari 19 turn (47%)** dan **6 dari 14 retry (43%)**
  terjadi sesudah penolakan itu, dan isinya seluruhnya mekanika:
  `TypeError: __init__() got an unexpected keyword argument 'env'` (LV-06),
  `FileNotFoundError: /testbed/repro_project`, **2× `app failed to become ready`** (LV-06),
  lalu 2× `REPRO_STATUS: PASS` sebelum akhirnya lolos di t19.
  **Yang membuat case ini paling mahal di korpus meski run-nya hijau:** ongkosnya tidak
  berhenti di fase REPRODUCE. Repro in-process yang ditolak punya **nol** kemunculan
  `pipe_runtime`; repro yang akhirnya dibekukan **mengimpor `pipe_runtime` di baris 4**.
  Penolakan judge di sini karenanya adalah sebab langsung keterpaparan LV-09 di fase FIX,
  yang lalu jadi sebab langsung pelanggaran LV-11. Di Catatan penutup 12915 butir 4, rantai
  ini masih ditulis sebagai *kemungkinan* ("kalau r1 yang lolos gate..."); di 12286 lemparan
  koinnya mendarat di sisi itu dan rantainya **terealisasi utuh dalam satu case**.
- **Bukti penguat (case kelima — dan yang pertama di mana penolakan judge bisa ditunjuk
  sebagai sebab langsung sebuah verdict GAGAL, bukan cuma churn) — django-11039**, run
  `r-dev--django__django-11039--r1` **dan** `--r2` (temuan bot-01, 2026-07-20).
  **Judge menolak di 2 dari 2 run, dan di kedua run exec-pair hijau sudah disaksikan lebih
  dulu.** Bukti: r1 `console.log` baris 830 (`checkpoint saved`), 858–862 (exec-pair 2 run
  segar, dua-duanya `output_transaction: True` + `REPRO_STATUS: FAIL`, exit 0), 864–869
  (temuan `[judge]` + `DONE deferred`); r2 baris 1171 (`checkpoint saved`), 1195–1211
  (exec-pair hijau), 1213–1221 (`[judge]` + `DONE deferred`). `events.jsonl` kedua run:
  satu event `done-deferred: independent review found issues`.
  - **Kategori aturan berbeda di dua run, dan itu penting untuk desain (b).** Di **r2**
    temuannya **murni `mechanics`** — judge mengutip *"when the behavior depends on how the
    program is launched, your script spawns that launch as a real child process"* dan
    *"specifically mandates the use of `pipe_runtime.App`"*. Jadi **(b) sebagaimana tertulis
    akan menyelamatkan r2**; ini case **ketiga** setelah 12915 dan 12286 di mana (b) tepat
    sasaran. Di **r1** temuannya **campuran**: satu butir `app-runtime` (mechanics) dan satu
    butir *"predicate tests the observable the user complains about"* (correctness) — jadi
    (b) hanya menyaring separuhnya, dan LV-13(a) tetap yang lebih luas.
  - **Ongkos r1 = seluruh run.** Checkpoint r1 (in-process, `connections` di-patch dengan mock
    yang `features.can_rollback_ddl = False`, assert `cmd.output_transaction is True → FAIL`)
    **memenuhi gold**: dengan gold patch, `migration.atomic and connection.features.
    can_rollback_ddl` = `True and False` = `False` → cabang PASS. Flip base FAIL → gold PASS
    akan lolos. *(Verifikasi ini tekstual — dibaca dari gold.patch dan dari script — bukan
    hasil eksekusi ulang; tapi jalurnya tunggal dan tidak ada cabang lain yang bisa dilewati.)*
    Setelah ditolak, model membangun **backend database sintetis di disk** dengan
    `class DatabaseWrapper(...): features = DatabaseFeatures()` sebagai **class attribute** —
    yang ditimpa `BaseDatabaseWrapper.__init__` lewat `self.features = self.features_class(self)`,
    sehingga `can_rollback_ddl` tetap `True` dan **gold patch tidak mengubah apa pun**.
    Hasil: `flip={'base': 'FAIL', 'patched': 'FAIL'}`, verdict **`wrong-logic`** dengan alasan
    *"likely gold-unsatisfiable predicate"* (`console.log` baris 1538). **Predikat yang
    gold-unsatisfiable itu lahir di dalam desain yang judge sendiri diktekan** — di r2 judge
    bahkan menuliskannya secara harfiah: *"the script should use a mock or a custom database
    backend/setting that ensures the child process sees `can_rollback_ddl = False`"*.
  - **Yang ini tambahkan di atas 12915:** di 12915 A/B-nya adalah *judge menolak vs tidak
    menolak*. Di 11039 judge menolak di dua-duanya, dan yang berbeda hanyalah **seberapa
    beruntung tebakan backend sintetis pengganti**. Jadi selain "presedensi vonis diberikan ke
    komponen yang tidak stabil", ada klaim yang lebih keras: **penolakan judge memindahkan run
    dari ruang desain yang terbukti bekerja ke ruang desain yang belum diuji siapa pun**, dan
    di 1 dari 2 lemparan ruang baru itu mengandung bug yang menggugurkan run.
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
- **Bukti penguat (case kedua, independen — kelas "`start()` gagal ready", 4×) —
  django-12915**, run `r-dev--django__django-12915--r1` (temuan bot-01, 2026-07-20).
  `events.jsonl` retry ke-4 s/d ke-7, keempatnya identik: `RuntimeError: pipe_runtime: app
  failed to become ready (application exited before printing the ready line)`. Skenarionya
  sama bentuknya dengan 13660: **satu request ASGI sekali jalan**, bukan server berumur
  panjang — prosesnya memang harus mati setelah menangani satu scope. Model akhirnya lolos
  dengan trik yang sama seperti r1/r2 13660: menyuntik `print("Ready")` artifisial di baris
  pertama `runner.py` semata-mata agar `App.start()` mau lewat (`r1/files/repro.py`).
  Kelas "one-shot vs ready line" kini **2 case, 6 kejadian**. Catatan penting soal sebab:
  model tidak memilih `pipe_runtime` sendiri — ia didorong ke sana oleh penolakan judge
  (LV-05), setelah lebih dulu punya repro in-process yang sudah terbukti hijau.
- **Bukti penguat (case ketiga — kedua kelas sekaligus, dalam satu run) — django-12286**,
  run `r-dev--django__django-12286--r1` (temuan bot-01, 2026-07-20). Dari `events.jsonl`:
  - Kelas **"API `App` dihalusinasi" — 1×**: `TypeError: __init__() got an unexpected
    keyword argument 'env'`. Ini **nama keenam** setelah `text=`, `capture_output=`,
    `.stdout`, `.process`, `.logs` — dan sekali lagi ia menambal lubang yang sama:
    tidak ada cara yang didukung untuk mengatur/membaca lingkungan proses anak.
  - Kelas **"`start()` gagal ready pada perintah one-shot" — 2×**: `RuntimeError:
    pipe_runtime: app failed to become ready (application exited before printing the ready
    line)`. Skenarionya sekali lagi one-shot — `manage.py check`, yang memang harus mati.
  Jalan memutarnya juga bentuk yang sama seperti 13660 dan 12915: `files/repro.py` final
  memakai `ready_token="CHECK_FINISHED"`, yaitu **token buatan sendiri yang dicetak wrapper
  anak setelah pekerjaannya selesai**, semata-mata agar `App.start()` mau lewat. Ditambah
  satu lapis lagi yang khas lubang output: model membungkus `app.start()/app.stop()` dengan
  redireksi `sys.stdout` ke `StringIO` untuk **menangkap kembali baris yang di-echo `App`** —
  persis kanal yang `app.output()`/`app.lines()` di usulan lever ini akan sediakan.
  Kelas "one-shot vs ready line" kini **3 case, 8 kejadian**; kelas halusinasi API **6 nama**.
- **Bukti penguat (case keempat + sweep frekuensi seluruh korpus) — django-11039 dan
  tabulasi lintas-case** (temuan bot-01, 2026-07-20). Dari `events.jsonl` 11039:
  - Kelas **"`start()` gagal ready pada perintah one-shot"** muncul lagi dengan **nama error
    ketujuh**: `ValueError: ready_token is required` (r1). Bentuknya beda — bukan proses mati
    duluan, melainkan `App.__init__` menolak dibuat tanpa `ready_token` — tapi lubangnya
    persis sama: `sqlmigrate` adalah perintah sekali-jalan yang tidak punya ready line, dan
    API tidak menyediakan cara menjalankannya.
  - Kelas **halusinasi/salah-pakai kwargs** muncul **3×** (r1: `capture_output`; r2:
    `capture_output`, `text`).
  **Angka lintas-korpus (sweep `events.jsonl` seluruh 120 run `r-dev`, 65 di antaranya
  qualified):**
  - Kelas **"one-shot vs ready line"** (`app failed to become ready` + `ready_token is
    required`): **27 kejadian, 15 run, 5 case** (11039, 11422, 12286, 12915, 13660). Entri ini
    sebelumnya mencatat "3 case, 8 kejadian" — angka sebenarnya **lebih dari tiga kali lipat**.
    Ini kelas kegagalan REPRODUCE terbesar kedua di korpus.
  - Kelas **`__init__() got an unexpected keyword argument`**: **33 kejadian, 21 run, 8 case**;
    **30 dari 33 hanya dua nama**, `text` (16×, 5 case) dan `capture_output` (14×, 5 case).
    Sisanya `env` (12286), `field_name` (10914), `app_path` (11797).
- **Catatan atribusi yang jujur, dan ia sekaligus menutup satu kandidat lever yang
  menggantung.** `text=` dan `capture_output=` **ambigu**: keduanya kwarg sah `subprocess.run`
  di Python 3.7+, dan keduanya juga ditebak model untuk `App`. Di 13660 mereka dicatat sebagai
  halusinasi API `App`; di 11039 model mendiagnosis sendiri sebaliknya (`console.log` r1 baris
  1121: *"The environment is using Python 3.6, where `subprocess.run` does not support
  `capture_output` or `text`"*). **Catatan penutup 12915 butir 6** menggantungkan kandidat
  lever *"model menargetkan Python modern, testbed Python 3.6"* dengan syarat: naikkan jadi
  entri kalau muncul di case ketiga. Syarat itu **terpenuhi** (5 case, 30 kejadian) — tetapi
  vonisnya tetap **BUKAN entri baru**, dan alasannya bukan frekuensi melainkan aturan main #4:
  **kedua pembacaan bermuara pada usulan lever yang sama persis**, yaitu menyediakan satu cara
  yang didukung untuk menjalankan perintah sekali-jalan dan **membaca kembali outputnya**
  (`App.run_once()` + `app.output()` di entri ini). Begitu itu ada, model tidak punya alasan
  menebak `capture_output=` pada `App` **maupun** meraih `subprocess.run` modern. Satu
  mekanisme, satu lever. Yang berubah adalah bobotnya: dengan 30 kejadian di 5 case, ini
  bukan lagi ekor panjang.
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
- **Titik data kedua (kali ini tidak merugikan) — django-12286**, run
  `r-dev--django__django-12286--r1` (temuan bot-01, 2026-07-20). `console.log` baris 738
  mendeklarasikan `PASS_OBSERVABLE: translation.E004` — bukan token kanonik, melainkan
  potongan pesan error; driver menerimanya, dan baris 1740 mencatat `DONE at turn 19
  (last attempt 14); pass observable verified: 'translation.E004'`. Bedanya dengan r3 13660:
  string yang dipilih di sini memang muncul di script dan flip tetap benar
  (base FAIL → gold PASS), jadi tidak ada kerugian. Nilainya sebagai bukti: cacat
  **"driver menerima observable PASS sembarang" bukan one-off** — ini kemunculan kedua di
  korpus, dan di kemunculan pertama ia yang menggugurkan run. Sekaligus ia menunjukkan
  ketegangan desain yang disebut di Catatan di bawah dengan konkret: `translation.E004`
  adalah observable yang **berguna untuk anti-konfabulasi** (ia bisa digrep ke source
  container) tetapi **tidak sah sebagai token vonis**. Dua peran itu memang bisa dipisah,
  dan case ini adalah contoh paling bersihnya.
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
- **Bukti penguat (case ketiga — dan di sini kerugiannya bisa dikuantifikasi persis, karena
  run tetangga membuktikan checkpoint-nya SUDAH cukup) — django-12915**, run
  `r-dev--django__django-12915--r1` (temuan bot-01, 2026-07-20). `console.log` baris 539
  menyimpan `files/repro-first-fail.py`; setelah penolakan judge di baris 574, model
  mengembara **16 turn (t11–t26)** dan tidak pernah kembali, berakhir `wrong-logic`.
  **Yang membuat case ini istimewa:** script yang dibuang itu praktis sama dengan
  `r-dev--django__django-12915--r2/files/repro.py` — yang di run berikutnya **lolos gate,
  lolos judge, dan menjadi yardstick yang membawa case ini sampai `resolved=true`**. Jadi
  bukan sekadar "checkpoint mungkin cukup baik"; di korpus ini ada bukti langsung bahwa
  bentuk itu **cukup untuk memenangkan seluruh pipeline**. Ambang N=4 yang diusulkan entri
  ini akan memicu tepat di t15, saat model sedang mengulang `app failed to become ready`
  untuk ketiga kalinya.
- **Bukti penguat (case keempat — dan di sini kerugiannya bukan turn, melainkan KELAS repro
  yang dibekukan) — django-12286**, run `r-dev--django__django-12286--r1` (temuan bot-01,
  2026-07-20). `console.log` baris 705 menyimpan `files/repro-first-fail.py` — in-process
  murni, exec-pair hijau, nol `pipe_runtime`. Setelah penolakan judge di baris 781, model
  mengembara **9 turn (t11–t19)** dan tidak pernah kembali; yang dibekukan adalah script
  berbasis `App` + subprocess + project sintetis di disk. Run-nya lolos, jadi kerugian
  langsungnya nol turn-vonis — **tapi justru penggantian kelas itu yang memindahkan case ini
  ke jalur LV-09 (5 `ModuleNotFoundError` di fase FIX) dan LV-11 (repro beku ditimpa model)**.
  Ambang N=4 yang diusulkan entri ini akan memicu tepat di t15, saat model mengulang
  `app failed to become ready` untuk kedua kalinya. Pola **"checkpoint yang dibuang lebih
  baik daripada penggantinya" kini 4 dari 4 case** (13660, 13230, 12915, 12286) — dan di
  12286 "lebih baik" bisa dinyatakan tanpa selera sama sekali: checkpoint-nya kebal LV-09
  secara struktural, penggantinya tidak.
- **Bukti penguat (case kelima — dan yang paling telak sejauh ini, karena "checkpoint lebih
  baik" di sini berarti "checkpoint LOLOS dan penggantinya GUGUR") — django-11039**, run
  `r-dev--django__django-11039--r1` (temuan bot-01, 2026-07-20). `console.log` baris 830
  menyimpan `files/repro-first-fail.py`; setelah penolakan judge di baris 869, model mengembara
  **7 turn (t11–t17)** dan tidak pernah kembali. Bedanya dengan empat case sebelumnya:
  **checkpoint yang dibuang itu memenuhi gold, penggantinya tidak.** Checkpoint mem-patch
  `connections` dengan mock yang `features.can_rollback_ddl = False` dan mengassert
  `cmd.output_transaction is True → FAIL`; di dunia gold nilai itu menjadi `False` → PASS, jadi
  flip lolos. Pengganti yang dibekukan memakai backend sintetis dengan `features` sebagai
  **class attribute**, yang ditimpa `BaseDatabaseWrapper.__init__`, sehingga gold patch tidak
  mengubah apa pun → `flip: base FAIL, patched FAIL` → verdict **`wrong-logic`**. *(Klaim
  "checkpoint memenuhi gold" ini verifikasi tekstual dari gold.patch + script, bukan eksekusi
  ulang.)* Ambang N=4 yang diusulkan entri ini akan memicu tepat di t15, saat model sedang
  bergulat dengan `ModuleNotFoundError` backend sintetisnya sendiri.
  Pola **"checkpoint yang dibuang lebih baik daripada penggantinya" kini 5 dari 5 case**
  (13660, 13230, 12915, 12286, 11039) — dan 11039 adalah yang pertama di mana selisihnya
  adalah selisih **lolos vs gugur**, bukan turn atau kelonggaran yardstick.
  Titik data kedua di case yang sama: **r2 juga membuang checkpoint-nya** (baris 1171,
  in-process, mematikan `can_rollback_ddl` pada koneksi Django sungguhan) setelah penolakan
  judge, lalu mengembara **8 turn (t15–t21)**. r2 lolos, tapi yardstick bekunya lebih longgar
  daripada checkpoint yang dibuang (LV-01, bukti penguat keenam). Jadi di **satu case**, dua
  run, checkpoint dibuang **2 dari 2 kali**, dan dua-duanya merugikan — sekali dengan
  menggugurkan run, sekali dengan melonggarkan alat ukur.
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
- **Bukti penguat (titik korelasi keempat — dan ia menambah temuan yang tidak nyaman:
  keterpaparan LV-09 ditentukan lemparan koin) — django-12915** (temuan bot-01,
  2026-07-20). Di case ini dua run REPRODUCE atas bug yang sama menghasilkan dua kelas
  repro yang berbeda, semata-mata karena judge menolak di satu run dan tidak di run lain
  (LV-05): `r-dev--django__django-12915--r1/files/repro.py` **mengimpor `pipe_runtime`**
  (`from pipe_runtime import App`), sedangkan `--r2/files/repro.py` **nol kemunculan**
  string `pipe_runtime` (in-process murni). Yang lolos gate kebetulan r2, sehingga fase FIX
  menerima repro yang bersih — dan hasilnya konsisten dengan tiga case sebelumnya:
  `f-dev--django__django-12915--r1/console.log` **0 kemunculan** `ModuleNotFoundError`,
  fase FIX selesai **2 turn, 1 attempt, `win`**, `resolved=true`.
  **Yang baru dan penting:** kalau r1 yang lolos gate, repro beku itu akan diawali
  `from pipe_runtime import App` dan fase FIX 12915 akan mendarat persis di kelas 11910 —
  di case yang, sebagaimana terbukti, sebetulnya bisa diselesaikan dalam 2 turn. Jadi
  LV-09 bukan cuma "bug yang menunggu case yang tepat": ia menunggu **run** yang tepat,
  dan di case yang sama peluangnya di korpus ini 1 dari 2.
- **Bukti penguat (titik korelasi kelima — dan yang pertama di mana kelas ini menggigit fase
  FIX yang toh berakhir hijau) — django-12286** (temuan bot-01, 2026-07-20). Repro beku
  `r-dev--django__django-12286--r1/files/repro.py` diawali `from pipe_runtime import App`
  di **baris 4**. Angka keras di `f-dev--django__django-12286--r1`:
  - **5 traceback `ModuleNotFoundError: No module named 'pipe_runtime'`** di `console.log`
    (baris 413, 536, 631, 689, 861) — yaitu **setiap** kali repro beku dijalankan di
    container kerja, tanpa satu pun pengecualian. Ditambah 2 kemunculan string yang sama di
    dalam komentar model sendiri, total **7 kemunculan** di console.
  - **5 dari 12 event `retry`** di `events.jsonl` berbunyi persis `repro run exited 1 without
    REPRO_STATUS: PASS; last output line: ModuleNotFoundError: No module named 'pipe_runtime'`.
  - Fase FIX tetap menang di **attempt 1, turn 7** — tetapi patch yang menang sudah ditulis
    di **t3** (`console.log` baris 408, `[driver] wrote /testbed/django/core/checks/
    translation.py`) dan **tidak berubah sedikit pun sesudahnya**. Artinya **4 dari 7 turn
    (t4–t7) habis semata-mata untuk melawan modul yang hilang**, bukan untuk memperbaiki
    Django. Ini rasio hangus tertinggi kedua di korpus setelah 11910, dan ia terjadi di run
    yang di papan skor terbaca sempurna.
  Korelasi lintas **lima** case kini konsisten dan searah: repro mengimpor `pipe_runtime` →
  FIX membakar mayoritas turn-nya di `ModuleNotFoundError` (11910: 588 kejadian / 80 turn
  tanpa hasil; 12286: 5 kejadian / 4 dari 7 turn); repro bersih → FIX selesai 2–4 turn
  (11099, 13230, 12915).
  **Fakta baru yang paling penting dari case ini — model tidak sekadar gagal, ia MENGGANTI
  ALAT UKURNYA:** menghadapi yardstick yang mati, model membangun tiga pengganti berturut-turut
  — `verify_fix.py` buatan sendiri (ditulis ulang **3×**), rekonstruksi manual `repro_project/`
  lalu `cd /testbed/repro_project && python manage.py check`, dan akhirnya **menimpa
  `/testbed/.pipe/repro.py` itu sendiri** dengan versi tanpa `pipe_runtime`. Rincian dan
  vonis atas perilaku itu dicatat sebagai bukti penguat di **LV-11**, karena mekanismenya
  ada di sana. Yang relevan untuk entri ini: LV-09 tidak hanya membakar turn — ia
  **menciptakan tekanan mekanis langsung ke arah pelanggaran integritas yardstick**, dan
  tekanan itu bahkan datang dari pesan penolakan driver sendiri, yang menyuruh model
  *"run `python /testbed/.pipe/repro.py` and get `REPRO_STATUS: PASS`"* di dunia tempat
  perintah itu mustahil dipenuhi secara jujur.
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
  - *Klarifikasi bertanggal 2026-07-20 (bot-01) — koreksi atas pembacaan analis sebelumnya
    terhadap django-12286.* Pembacaan itu menyimpulkan bahwa karena bug ini, agen FIX
    "menulis ulang repro-nya sendiri lalu memvalidasi diri dengan script buatannya, sehingga
    sinyal repro lulus di fase FIX berasal dari script buatan model, bukan repro tersanksi —
    ini melemahkan validitas fase FIX". **Kesimpulan itu overclaim, dan sudah diverifikasi
    salah di kode.** Rumusan yang benar: bug ini merusak **loop iterasi model**, bukan
    **validitas vonis**. Buktinya, semuanya di jalur DONE/gate:
    - `harness/stages/run_fix_gemma.py` baris 30 mengimpor `evaluate_patch_in_fresh_world`,
      dan baris 303–305 memakainya untuk pre-check DONE dengan argumen
      `args.input_repro_files` — yaitu **direktori artefak BEKU fase R di host**, bukan file
      mana pun di container kerja yang sedang dipegang model.
    - `harness/stages/run_fix_gates.py` baris 23 dan 88 memanggil fungsi yang **sama** dengan
      argumen yang **sama**. Pre-check dan gate karenanya memakai **standar tunggal**, bukan
      dua standar — persis invarian yang katalog ini pertahankan di tempat lain.
    - `harness/stages/repro_sandbox_runner.py` baris 25–37 me-mount direktori beku itu sebagai
      `/pipe-in:ro` di container segar, lalu menyalin **`repro.py` DAN `pipe_runtime.py`**
      ke `/testbed/.pipe`. Direktori artefak fase R memang berisi `pipe_runtime.py`
      (`r-dev--django__django-12286--r1/files/pipe_runtime.py`, 9.781 byte).
    Jadi DONE hanya diterima ketika **repro beku lolos di dunia segar yang PUNYA
    `pipe_runtime`** — dunia yang justru tidak pernah kekurangan modul itu, karena kekurangan
    itu spesifik milik container kerja. Vonis `flip` di `f-dev--django__django-12286--r1`
    (`gate_runs.json`: `status1=PASS, status2=PASS, exit 0/0`) karenanya **SAH**, dan
    `resolved=true` yang menyusulnya sah juga. Yang rusak adalah alat ukur yang dipegang
    model **selama** ia bekerja: ia kehilangan umpan balik, sempat tersesat memvalidasi diri
    dengan script buatannya sendiri, dan membakar 4 dari 7 turn — tetapi tak satu pun dari
    itu pernah menjadi vonis. Konsekuensi untuk prioritas: entri ini tetap **UTAMA**, hanya
    saja alasannya adalah **pemborosan dan tekanan ke arah tampering**, bukan kebocoran gate.
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
- **Bukti penguat untuk bagian (b) — kali ini dari sisi yang berlawanan, dan terverifikasi
  di kode — django-12915**, run `r-dev--django__django-12915--r1` (temuan bot-01,
  2026-07-20). Di 11910 keluhannya adalah *kontrak tidak punya kata untuk "tidak tahu"*.
  Di 12915 ternyata **model sudah menciptakan kata itu sendiri**: `repro.py` di r1 **dan**
  r2 sama-sama punya cabang ketiga yang mencetak `REPRO_STATUS: ERROR` untuk exception yang
  tak dikenali — model membedakan "aku tak berhasil mengamati" dari PASS/FAIL tanpa diminta.
  Yang tidak punya kata itu adalah **harness**:
  - `harness/stages/reproduce_gates.py` baris 11:
    `_STATUS_RE = re.compile(r"^REPRO_STATUS: (PASS|FAIL)\s*$", re.MULTILINE)` — pola yang
    sama di `harness/stages/gemma_protocol.py` baris 244. `ERROR` **tidak terlihat sebagai
    token sama sekali**, bukan "terlihat lalu ditolak".
  - Akibat #1 (mid-loop, **4×**): `events.jsonl` retry ke-8 s/d ke-11, semuanya
    `repro run exited 0 without REPRO_STATUS: FAIL; last output line: REPRO_STATUS: ERROR`.
    Model tidak pernah diberi tahu apa yang salah, dan salah menebaknya sendiri — `console.log`
    baris 1543: *"The `REPRO_STATUS: ERROR` occurred because `app.wait_for` might have missed
    the error message ... if the timing was off"* (sebenarnya bukan timing).
  - Akibat #2 (vonis, **1×**, dan ini yang paling merusak): flip gagal dengan alasan
    `no REPRO_STATUS token in gold-patched run output` (`reproduce_gates.py` baris 84)
    **padahal `flip_run.json` berakhir dengan baris `REPRO_STATUS: ERROR`**. Diagnosis yang
    dicetak harness **salah secara faktual, dan salahnya by construction** — konsekuensi
    langsung dari kosakata dua-nilai di baris 11.
  - Akibat #3 (label): `harness/stages/run_repro_gates.py` baris 105 memetakan **setiap**
    kegagalan flip ke verdict `wrong-logic`. Sebab sebenarnya di sini adalah *environment
    repro yang rusak di sisi gold* — `ROOT_URLCONF='django.conf.urls'` (modul tanpa
    `urlpatterns`) plus `test.txt` yang tak pernah dibuat, sehingga run gold-patched jatuh
    Http404 → `response_for_exception` → `technical_404_response` → `ImproperlyConfigured`.
    Di papan skor itu terbaca sebagai "logika predikat model salah". Ini **persis** jenis
    penyamaran yang jadi alasan (a) mengusulkan verdict terpisah `repro-not-armed`,
    hanya di fase yang berbeda.
  Konsekuensi untuk desain: bagian (b) sebaiknya tidak dibaca lagi sebagai "ajari model
  menulis ERROR" melainkan sebagai **"ajari parser membaca ERROR"** — perubahannya satu
  regex plus satu cabang penanganan, jauh lebih murah daripada perkiraan awal entri ini,
  dan tanpa itu setiap repro yang berlaku benar akan didiagnosis salah.
- **Bukti penguat — django-12286** (temuan bot-01, 2026-07-20), menyentuh kedua bagian:
  - Untuk **(b)**: repro beku 12286 mengulang tanda tangan 11910 dengan bentuk berbeda —
    `except Exception as e: print(f"Execution failed: {e}")` di wrapper anak, lalu pemanggil
    menerjemahkan "output tanpa `translation.E004`" menjadi `REPRO_STATUS: PASS`. Sekali lagi
    **kegagalan environment tidak bisa dibedakan dari perbaikan yang benar**, dan sekali lagi
    di repro yang lolos gate dan dipakai sampai vonis (rincian di LV-01, bukti penguat kelima).
    **Yang menahan kelas ini dari menggigit di sini murni kebetulan letak:** modul yang hilang
    membuat `from pipe_runtime import App` di **baris 4** mati dengan exit 1 **sebelum** cabang
    penelan sempat dieksekusi, sehingga driver melihat error, bukan PASS palsu. Kalau
    dependency-nya putus satu lapis lebih dalam — misal di dalam `run_check.py` yang dijalankan
    sebagai anak — repro yang sama akan mencetak `REPRO_STATUS: PASS` di container FIX yang
    **belum disentuh sama sekali**, yaitu persis skenario 11910. Jadi 12286 bukan bukti bahwa
    kelas ini jinak; ia bukti bahwa keselamatannya bergantung pada **di baris berapa** dunia
    itu pecah.
  - Untuk **(a)**: gerbang pre-flight akan memotong run ini di detik pertama dengan diagnosis
    yang benar (`repro-not-armed`), menghemat 4 dari 7 turn FIX **dan** — ini yang lebih
    penting — menghapus seluruh tekanan yang mendorong model menimpa repro beku (LV-11).
    Ini case kedua setelah 11910 di mana (a) tepat sasaran, dan yang **pertama** di mana
    ongkosnya harus dibaca dari run yang papan skornya hijau sempurna.
- **Bukti penguat untuk bagian (b) — django-11039, dan ini rekaman paling rapat di korpus
  atas MEKANISME degradasinya, bukan cuma akibatnya** (temuan bot-01, 2026-07-20).
  Di 11910 yang tercatat adalah akibat (cabang error jatuh ke PASS); di 12915 yang tercatat
  adalah sebabnya di kode (parser dua-nilai). Di 11039 **seluruh rantainya terekam dalam satu
  run, tiga langkah berturut-turut**, semuanya di `r-dev--django__django-11039--r1/console.log`:
  1. **t15 (baris 1356):** model menulis cabang jujur —
     `print("REPRO_STATUS: ERROR (Command failed)")` untuk kasus child process gagal.
  2. **baris 1408 → `events.jsonl` retry terakhir:** cabang itu benar-benar menyala, dan
     driver membalas `repro run exited 0 without REPRO_STATUS: FAIL; last output line:
     REPRO_STATUS: ERROR (Command failed)`. Yaitu: **pesan yang sama persis dengan pesan untuk
     script yang tidak mencetak status sama sekali.** Model tidak diberi tahu bahwa masalahnya
     adalah kosakata; ia hanya diberi tahu bahwa outputnya salah.
  3. **t16 (baris 1476):** model membuang prefiks kanoniknya dan menggantinya dengan
     `print("Command failed, cannot determine status")` — cabang itu kini **tidak mencetak
     `REPRO_STATUS` sama sekali**. Itulah bentuk yang dibekukan sebagai `files/repro.py` r1.
  Lalu di **r2** cabang itu **hilang sepenuhnya**: `if "BEGIN" in stdout and "COMMIT" in
  stdout: FAIL else: PASS`, tanpa penjaga apa pun. Jadi urutannya: **token jujur → pesan
  tanpa token → cabangnya dihapus dan semua kegagalan katastrofik mendarat di PASS.**
  **Dua hal yang TIDAK boleh diklaim dari ini, dan pemisahannya penting:**
  - Langkah 1→3 adalah **sebab-akibat yang terekam** di dalam satu run: driver menolak, model
    mengubah cabang itu di turn berikutnya. Ini bukti kausal.
  - Langkah r1→r2 **bukan pembelajaran**: r2 adalah run segar tanpa memori r1. Yang benar
    dikatakan: tekanan yang sama dijatuhkan dua kali dan mendarat di dua tempat berbeda, dan
    karena kita **rerun sampai qualified**, script yang akhirnya dibekukan ditarik dari
    distribusi yang sudah digeser ke arah permisif. Klaim *"gate menyeleksi repro yang lebih
    lemah"* **tidak didukung sebagai mekanisme** di case ini — r1 gugur karena predikat
    gold-unsatisfiable (LV-05/LV-08), sama sekali bukan karena penjaganya. Yang didukung
    bukti adalah pernyataan yang lebih sempit dan lebih bisa dipertahankan: **loop retry
    menggeser distribusi bentuk repro ke arah permisif, dan rerun-sampai-lolos mengambil
    sampel dari distribusi yang sudah bergeser itu.**
- **Frekuensi kosakata "tidak tahu" di korpus (sweep bot-01, 2026-07-20)** — angka ini
  menggantikan "n=1 (12915)" sebagai basis bagian (b): **model menciptakan status ketiga atau
  menolak mencetak status di 5 dari 23 case** yang punya repro qualified. Rinciannya:
  `REPRO_STATUS: ERROR` (12915 r1 & r2, 13768 r3, 11422 r43), `REPRO_STATUS: ERROR_ENVIRONMENT`
  (10914 r1), `REPRO_STATUS: ERROR (Command failed)` (11039 r1), plus **dua kasus di mana model
  sengaja TIDAK mencetak status** ketika kontrol positifnya gagal, lengkap dengan komentar yang
  menjelaskan alasannya (`11422 r44`: *"Do not return REPRO_STATUS here"*; `13768 r4`:
  *"We do not print REPRO_STATUS here to avoid false positives/negatives"*). **Tak satu pun
  dari tujuh bentuk itu bisa dilihat `_STATUS_RE`.** Kesimpulan yang layak dinaikkan: ini bukan
  kekurangan yang harus "diajarkan" ke model — model sudah menuliskannya sendiri, berulang
  kali, di case-case yang tak berhubungan. Yang kurang adalah pembacanya.
- **Bukti penguat untuk bagian (b) — TRIO 14238 / 13590 / 14382, dan ini yang PERTAMA
  memberi bentuk tepat pada (b): masalahnya bukan "jatuh ke PASS", melainkan "dibulatkan
  ke salah satu dari dua vonis"** (temuan bot-01, 2026-07-20). Sampai sekarang (b)
  dirumuskan satu arah — *cabang error jatuh ke PASS*. Tiga run yang selesai berurutan
  memberi ketiga polaritas dalam satu jendela, dan **kedua pembulatan sama-sama merusak,
  hanya ke arah yang berlawanan**:
  1. **`else: PASS` → lulus palsu.** `r-dev--django__django-14238--r1` baris 82–83.
     Diverifikasi eksekusi: Django tak bisa di-import → `REPRO_STATUS: PASS`
     (empat kelas sabotase, empat PASS; rincian di LV-01 bukti kesepuluh dan KH-07).
  2. **`else: FAIL` → run yang dihancurkan di gerbang.** `r-dev--django__django-14382--r1`
     baris 28–30 (`else: print("Unexpected output: ..."); print("REPRO_STATUS: FAIL")`).
     Repro memakai `target_dir = "testapp_dir/"` tetapi **tidak pernah membuat direktorinya**,
     jadi setelah gold diterapkan `startapp` gagal dengan
     `CommandError: Destination directory '/testbed/testapp_dir' does not exist` — dan cabang
     `else` menerjemahkan kegagalan setup itu menjadi **FAIL**, yaitu "bug masih ada".
     `flip_run.json` r1 (terlampir di artefak) menunjukkannya persis: base FAIL, gold FAIL.
     Verdict: `wrong-logic`, `pass_l1=false`. **Ini kejadian kedua kelas "repro
     gold-unsatisfiable" setelah `11039` r1** — tetapi sebabnya BEDA dan pemisahannya penting:
     di 11039 predikatnya sendiri yang tidak bisa dipuaskan gold (backend sintetis dengan
     `features` sebagai class attribute); di 14382 predikatnya baik-baik saja dan yang salah
     adalah **setup yang tidak lengkap plus fallback berpolaritas FAIL** yang menyembunyikannya.
     Per aturan main #3 keduanya tetap satu kelas di tingkat gejala (*flip tidak flip →
     `wrong-logic`*), jadi ini **bukti penguat, bukan entri baru**.
  3. **Nilai ketiga → gerbang bisa membedakan.** `r-dev--django__django-13590--r1` baris
     75–78 membungkus semuanya dengan `except Exception: print("REPRO_STATUS: UNKNOWN")`,
     dan itu **bekerja**: tiga dari empat kerusakan lingkungan mendarat di UNKNOWN, bukan
     di PASS dan bukan di FAIL.
  **Rumusan (b) yang seharusnya, dan ia lebih sempit sekaligus lebih mengikat daripada yang
  tertulis di atas:** yang wajib dituntut bukan *"jangan jatuh ke PASS"* melainkan
  **"keluaran untuk 'aku tidak berhasil mengamati' harus berupa token KETIGA yang tidak
  sama dengan PASS maupun FAIL"**. Menuntut `else: FAIL` sebagai perbaikan atas `else: PASS`
  akan **memindahkan** kerusakan dari papan skor ke laju gugur, bukan menghapusnya — dan
  14382 r1 adalah harganya, terbayar penuh.
- **Bukti penguat — dan ini KOREKSI ke arah yang tidak nyaman untuk usulan (b) itu sendiri:
  uji sabotase dinamis yang diusulkan (b) punya titik buta seukuran LV-01** (temuan bot-01,
  2026-07-20, dari `django-13590`). Usulan (b) di bawah berbunyi: *"sepenuhnya secara dinamis
  dengan menjalankan repro di container **tanpa** repo (sabotase sengaja): kalau ia mencetak
  PASS di sana, repro-nya cacat menurut konstruksi."* Diuji langsung pada 13590:
  - Django dibuat tak bisa di-import → **UNKNOWN**. Repro **lulus** uji (b). Sempurna.
  - Patch D1 (`return [...]`, selalu paksa ke `list`) → **PASS**.
  - Patch D2 (`return value`, sub-ekspresi tidak pernah diresolusi) → **PASS**.
  Jadi repro yang **lulus penuh uji (b)** tetap meloloskan dua patch yang merusak kontrak
  yang sedang diperbaiki. Uji sabotase-lingkungan mengukur **apakah alat ukurnya hidup**;
  ia sama sekali tidak mengukur **apakah alat ukurnya menunjuk ke hal yang benar**. Kedua
  hal itu terbukti **independen** di case ini. **Konsekuensi yang harus ikut dipasang
  bersama (b):** jangan pernah melaporkan "lulus uji sabotase" sebagai sertifikat kualitas
  repro; laporkan sebagai *"yardstick armed"*, dan sediakan sumbu kedua (LV-01: kontrol
  positif + assert atas nilai) sebagai kriteria terpisah yang tidak boleh dibulatkan ke
  dalamnya.
- **Angka pendukung untuk (b), diperbarui 2026-07-20 (bot-01, sesi ketiga):** sweep ulang
  seluruh `events.jsonl` di `artifacts/r-dev` (**126 run**) dengan regex yang sama seperti
  sweep sebelumnya:
  - `without REPRO_STATUS: FAIL; last output line: REPRO_STATUS: PASS` → **89 kejadian,
    15 run, 9 case** (naik dari 83/14/8; **seluruh tambahannya dari `14238` r1**, 6 kejadian).
  - `last output line: REPRO_STATUS: ERROR` → **9 kejadian, 4 run, 4 case** (naik dari 8/3/3;
    tambahannya dari `14382` r2, dan itu adalah **kontrol positif yang menyala**, bukan cacat).
  - `last output line: REPRO_STATUS: UNKNOWN` → **1 kejadian, 1 run, 1 case** — bentuk
    kosakata "tidak tahu" yang **kedelapan**, dan sekali lagi **tak terlihat `_STATUS_RE`**.
    Model kini sudah menciptakan token ketiga di **6 dari 27 case**. Argumen "yang kurang
    adalah pembacanya, bukan modelnya" bertambah satu titik.
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
- **Bukti penguat (case kedua — dan kali ini yardstick beku benar-benar DITIMPA, bukan
  ditambal) — django-12286**, run `f-dev--django__django-12286--r1` (temuan bot-01,
  2026-07-20). Urutannya terbaca lurus di `console.log`:
  - **t2–t4:** repro beku mati 5× dengan `ModuleNotFoundError` (LV-09). Model membangun
    yardstick tandingan **di luar** `/testbed/.pipe`: `verify_fix.py` buatan sendiri
    (ditulis ulang 3×, baris 457, 635, 721, 818) dan rekonstruksi manual `repro_project/`
    lalu `cd /testbed/repro_project && python manage.py check` (baris 434–444, 503–514).
  - **t5 (baris 920): `cat <<EOF > /testbed/.pipe/repro.py`** — model **menimpa repro beku**
    dengan versi buatannya sendiri yang membuang `pipe_runtime`, lalu menjalankannya:
    `REPRO_STATUS: PASS`, exit 0 (baris 1085), dan **mendeklarasikan DONE di atas PASS itu**.
    Motifnya ditulis terus terang di komentarnya sendiri: *"Since I cannot fix the
    environment's missing 'pipe_runtime', I will provide a modified version of the repro
    script that removes the dependency ... so that it can print 'REPRO_STATUS: PASS' as
    required."*
  - **t6:** model **menyesal dan mencoba mengembalikannya** — `git checkout --
    /testbed/.pipe/repro.py` → `error: pathspec ... did not match any file(s) known to git`.
    Perubahan itu **tidak bisa dibatalkan dari dalam container**, dan `repro.py` di container
    tetap versi model sampai run berakhir.
  Tiga hal yang case ini tambahkan, dan semuanya soal **desain pagarnya**:
  1. **Bentuknya substitusi, bukan mutasi.** Di 11910 modelnya `sed -i` (tambal); di sini
     penulisan ulang penuh, plus dua yardstick tandingan di luar `/testbed/.pipe`. Pagar
     yang hanya melarang *edit* atau meng-`chmod 0444` file beku **tidak menutup kelas ini**
     dengan bersih — `cat > file` atas file 0444 memang gagal, tapi model masih bisa
     mengukur diri dengan `verify_fix.py` dan mendeklarasikan DONE atas dasar itu. Yang
     benar-benar menutupnya adalah **verifikasi hash tepat sebelum menerima DONE**. Artinya
     bagian hash di usulan entri ini bukan "jaring terakhir", melainkan **yang utama**.
  2. **Pagar integritas yang menyelamatkan 11910 buta di sini.** Pre-check
     `off-candidate-files` menangkap `repro_project/*` dan `verify_fix.py` (2 event,
     `events.jsonl` msg_used 5 dan 6) tetapi **tidak pernah menyebut
     `/testbed/.pipe/repro.py`** — karena pagarnya berbasis diff git dan `/testbed/.pipe`
     tidak ter-track. Itu bukan dugaan: kegagalan `git checkout` di t6 membuktikannya
     langsung. Jadi kelas ini **secara struktural tak terlihat** oleh satu-satunya mekanisme
     integritas yang sekarang ada.
  3. **Sinyal di dalam container tercemar total, dan papan skor tidak mencatatnya.**
     `verdict.json` fase FIX berbunyi `flip`, `swebench_eval.json` `resolved=true`, F2P 1/1,
     P2P 7/7 — dan tidak ada satu artefak pun yang menyebut bahwa yardstick di container
     sudah ditulis ulang oleh pihak yang sedang diuji. Ia hanya ketahuan karena seseorang
     membuka `console.log` baris 920.
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
  - *Klarifikasi bertanggal 2026-07-20 (bot-01) — supaya entri ini tidak terbaca lebih jauh
    dari klaimnya, setelah django-12286.* Di 12286 model **benar-benar menimpa**
    `/testbed/.pipe/repro.py` dan **mendeklarasikan DONE di atas PASS dari file yang ia tulis
    sendiri**. Meskipun begitu, **vonis fase FIX tetap SAH**, dan itu bukan keberuntungan
    melainkan konsekuensi jalur kode: driver tidak pernah memakai file di container kerja
    sebagai dasar vonis. Pre-check DONE (`run_fix_gemma.py` baris 303–305) dan gate
    (`run_fix_gates.py` baris 88) sama-sama memanggil `evaluate_patch_in_fresh_world` atas
    **direktori artefak beku fase R** di host, yang di-mount `/pipe-in:ro` ke container segar
    berisi `repro.py` **dan** `pipe_runtime.py` (`repro_sandbox_runner.py` baris 25–37).
    Rincian lengkapnya di klarifikasi bertanggal di **LV-09**.
    **Rumusan yang tepat untuk seluruh kelas ini:** cacat "beku hanya konvensi" merusak
    **loop iterasi model** — alat ukur yang ia pegang saat bekerja — **bukan validitas
    vonis**; standar vonisnya tunggal, sama antara pre-check dan gate, dan berada di luar
    jangkauan model. Dua konsekuensi yang saling berlawanan, keduanya perlu dicatat:
    (i) alasan yang tertulis di baris Prioritas di bawah — *"melubangi integritas gate ...
    seluruh papan skor kehilangan makna"* — **tidak didukung oleh jalur kode sebagaimana ia
    berdiri sekarang**, jadi urgensi entri ini sebaiknya dibaca lebih rendah dari kata
    "tinggi" itu; (ii) sebaliknya, 12286 menaikkan bobot **LV-10(a)**, yang menyerang sebab
    (yardstick mati) alih-alih gejala (model menggantinya) — dan menghapus sebabnya
    menghapus motif tampering sekaligus. Kalau harus memilih urutan: **LV-09 dan LV-10(a)
    dulu; bagian hash dari entri ini menyusul sebagai audit, bukan sebagai penyelamat vonis.**
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
- **Bukti penguat untuk (A) — case kedua, klaim judge yang juga bisa dibantah dari artefak
  resmi — django-12915**, run `r-dev--django__django-12915--r1/console.log` baris 567–574
  (temuan bot-01, 2026-07-20). Judge menahan DONE dengan klaim bahwa repro in-process
  *"bypasses the actual ASGI server initialization and the specific environment ... that
  leads to the `NoneType` error"* dan menuntut server ASGI sungguhan sebagai child process.
  **Klaim itu terbantah dua kali, masing-masing dari sumber yang tidak bisa didebat:**
  1. Driver sendiri **sudah menyaksikan** exec-pair hijau atas script itu — 2 run segar,
     dua-duanya `REPRO_STATUS: FAIL` dengan `TypeError: 'NoneType' object is not callable`.
     Bug-nya jelas-jelas muncul tanpa server ASGI apa pun.
  2. Test resmi SWE-bench untuk case ini melakukan hal yang **persis sama**: `test_patch`
     di `swebench_spec.json` berisi `handler = ASGIStaticFilesHandler(ASGIHandler())` lalu
     `response = await handler.get_response_async(request)` — in-process, tanpa daphne,
     tanpa uvicorn, tanpa child process.
  Ongkosnya sudah dirinci di LV-05 (16 turn, 8 retry, verdict gagal). Yang relevan untuk
  entri ini: klaim judge di 12915 **bisa diverifikasi mesin dan hasilnya negatif**, sama
  seperti di 13230 — dan di kedua case driver tidak pernah memintanya. Titik (A) kini
  **n=2 dengan dua bantahan berbasis artefak**, bukan lagi n=1.
- **Titik data kedua untuk (B) — django-12286**, run `l-dev--django__django-12286--r1`
  (temuan bot-01, 2026-07-20). `gold_eval.json`: `pointed_lines: [11, 22]`,
  `line_overlap: false`, `file_match: true`, `criterion: shortlist-v2`, `qualified: true`.
  Slot `evidence` di `files/localize.md` berbunyi: *"In `django/core/checks/translation.py`,
  the `check_language_code` function (around line 18) checks
  `if language_code not in language_codes:`"*. **Dua kesalahan yang bisa dibantah mesin dari
  gold patch saja:** (i) uji keanggotaan yang dimaksud ada di
  `check_language_settings_consistent`, bukan di fungsi yang disebut — gold patch mengganti
  baris `if settings.LANGUAGE_CODE not in available_tags:` di hunk berheader
  `@@ -55,7 +56,9 @@`, jadi lokasinya ~56–63, sementara rentang 11–22 yang ditunjuk memuat
  pemeriksaan **format** kode bahasa (E001), bukan pemeriksaan **konsistensi** (E004);
  (ii) nama variabelnya `available_tags`, bukan `language_codes`.
  Tanda tangannya **persis sama dengan 13230**: nama simbol salah di file yang benar, rentang
  baris meleset ~40 baris, `line_overlap: false` direkam tapi tidak dikonsumsi siapa pun,
  kandidat tetap `qualified`, dan **kesimpulannya tetap benar** sehingga fase FIX
  menyelesaikannya tanpa terganggu (attempt 1, 7 turn, `gold_eval` fase FIX
  `line_overlap: true`).
  **Vonis 13230 tidak berubah** — ini bukan cacat kriteria; FIX menerima *file* kandidat,
  bukan rentang baris, dan rentang yang meleset tidak pernah membatasi apa pun. Yang
  bertambah adalah profil detektornya: **2 dari 2 case ber-`line_overlap: false` ternyata
  konfabulasi yang bisa dibuktikan salah dari artefak resmi, dan 2 dari 2 tidak merugikan
  hasil.** Itu tepat profil **instrumentasi** — sinyal yang akurat mendeteksi prosa yang
  salah, tetapi tidak berkorelasi dengan kegagalan — dan karenanya menguatkan keputusan
  (b) untuk mencatat `citation_mismatch` tanpa menggugurkan apa pun.
- **Titik data ketiga untuk (B) — django-13658**, run `l-dev--django__django-13658--r1`
  (temuan bot-01, 2026-07-20). `gold_eval.json`: `pointed_lines: [115, 130]`,
  `line_overlap: false`, `file_match: true`, `criterion: shortlist-v2`, `qualified: true`.
  Slot `evidence` di `files/localize.md` berbunyi: *"In `django/core/management/__init__.py`,
  the `ManagementUtility.__init__` method (around line 123) calls `CommandParser(usage=...)`"*.
  **Dibantah mesin dari gold patch dan dari sumbernya:** panggilan itu ada di
  `ManagementUtility.execute()`, bukan di `__init__` — header hunk gold berbunyi
  `@@ -344,7 +344,12 @@ def execute(self):`, dan `grep -n 'CommandParser(' /testbed/django/`
  di image case ini mengembalikan `__init__.py:347` (diverifikasi bot-01 di dalam image).
  `__init__` hanya menghitung `self.prog_name`. Jadi: **nama method salah di file yang benar,
  rentang baris meleset ~220 baris** — tanda tangan identik dengan 13230 (~50 baris) dan
  12286 (~40 baris), dan kali ini selisihnya yang terbesar.
  **Dan sekali lagi kesimpulannya tetap benar:** `what` dan `why` di `localize.md` menyatakan
  fix yang **persis sama dengan gold** (*"CommandParser should be instantiated with the `prog`
  argument set to `self.prog_name`"*), dan CANDIDATE 1 = file gold. Profil detektornya
  karenanya tidak berubah: **3 dari 3 case ber-`line_overlap: false` adalah konfabulasi yang
  bisa dibuktikan salah dari artefak resmi, dan 3 dari 3 tidak menyesatkan kesimpulannya.**
  **Yang BARU di case ini dan wajib dicatat supaya tidak salah dibaca:** 13658 adalah run
  pertama di mana sitasi LOCALIZE yang meleset **berdampingan dengan** fase FIX yang mendarat
  di file NON-gold (attempt 2, lihat autopsi di bawah). Menggoda untuk menghubungkan keduanya.
  **Hubungan itu tidak didukung bukti:** LOCALIZE menunjuk file gold sebagai CANDIDATE 1 dan
  FIX memang mencobanya lebih dulu selama 40 turn penuh; perpindahan ke CANDIDATE 2 adalah
  mekanisme fallback antar-attempt yang bekerja sebagaimana dirancang, bukan akibat rentang
  baris yang salah — rentang itu, seperti di 13230 dan 12286, tidak pernah membatasi apa pun.
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

---

## Entri baru — autopsi django-12915: full green dengan patch yang lebih buruk dari gold
## (bot-01, 2026-07-20)

**Korpus:** `artifacts/r-dev/r-dev--django__django-12915--r1` (gagal, `wrong-logic`),
`--r2` (qualified), `artifacts/l-dev/l-dev--django__django-12915--r1`,
`artifacts/f-dev/f-dev--django__django-12915--r1`.
Gold: `cases/gold/django__django-12915/gold.patch`. Bug: `StaticFilesHandlerMixin`
tidak punya `get_response_async`, sehingga `ASGIStaticFilesHandler` jatuh ke
`BaseHandler.get_response_async` dan menabrak `_middleware_chain = None`.

**Hasil (terverifikasi ulang dari artefak):** FULL GREEN.
`f-dev/.../swebench_eval.json` → `resolved=true`, `patch_successfully_applied=true`,
F2P **3/3** (`test_get_async_response`, `test_get_async_response_not_found`,
`test_static_file_response`), P2P **8/8**, `f2p_failed=[]`, `p2p_failed=[]`.
`swebench_test_output.log`: `Ran 11 tests ... OK`.

**Angka biaya per fase:**

- REPRODUCE r1: **26 turn, 11 attempt, 12 event retry**, verdict `wrong-logic`,
  `console.log` 2.119 baris. Rincian 12 retry: 2× error koding model
  (`module 'django.conf' has no attribute 'urls'`; `module 'asyncio' has no attribute 'run'`),
  **1× penolakan judge**, 4× `pipe_runtime: app failed to become ready`,
  4× `exited 0 ... last output line: REPRO_STATUS: ERROR`, 1× `PASS_OBSERVABLE not found`.
- REPRODUCE r2: **10 turn, 2 attempt, 1 retry**, verdict `pass`, console 541 baris.
- LOCALIZE: 1 retry (format `candidates.md`), `qualified=true`, `file_match=true`,
  `line_overlap=true`. Kandidat 1 = file gold.
- FIX: **2 turn, 1 attempt, `win`**, 1 penolakan DONE (`run repro first`), `flip`.

**Kelas kegagalan REPRODUCE r1 — semuanya sudah tercatat, tidak ada yang baru:**
LV-05 (1×, dan ia yang memicu 8 retry berikutnya), LV-06 (4×), LV-10b (4×),
LV-08 (checkpoint dibuang, 16 turn). Rinciannya sudah ditulis sebagai bukti penguat di
entri masing-masing. **Nol retry yang sebabnya "salah paham bug"** — konsisten dengan
13660 dan 13230; pemahaman model atas bug ini benar sejak turn-turn awal di kedua run,
dan `localize.md` menjelaskan mekanismenya dengan tepat sampai ke
`django/core/handlers/base.py:148`.

**Yang BARU di case ini, dan jadi alasan autopsi ini ditulis:** patch model **lolos L2
padahal secara non-fungsional lebih buruk dari gold** — lihat LV-14.

## LV-14 — Divergensi patch-vs-gold berhenti di file/baris; isinya tidak pernah dibandingkan

- **Asal-usul:** django-12915. Bukti:
  `artifacts/f-dev/f-dev--django__django-12915--r1/files/fix.diff` vs
  `cases/gold/django__django-12915/gold.patch`; `gold_eval.json` dan `swebench_eval.json`
  di run yang sama; `test_patch` di `cases/gold/django__django-12915/swebench_spec.json`.
- **Gejala (angka keras):** kedua patch menambahkan `get_response_async` ke
  `StaticFilesHandlerMixin`, di file yang sama, di titik sisip yang sama. Bedanya dua baris:
  - Gold: `return await sync_to_async(self.serve)(request)` dan
    `return await sync_to_async(response_for_exception)(request, e)` (plus import
    `from asgiref.sync import sync_to_async`).
  - Model: `return self.serve(request)` dan `return response_for_exception(request, e)`.
  Model menjalankan **file I/O sinkron di dalam `async def`**, di atas event loop —
  persis yang keberadaan `sync_to_async` di gold dimaksudkan mencegah. Toh hasilnya
  **F2P 3/3, P2P 8/8, `resolved=true`**, karena test suite resmi hanya memeriksa nilai:
  `status_code == 200`, `status_code == 404`, empat header, dan isi body. **Tidak ada satu
  pun test yang mengukur blocking.** Sinyal yang sudah dikumpulkan harness pun buta pada
  ini: `gold_eval.json` mencatat `file_match: true` dan `line_overlap: true` — dua-duanya
  hijau, dan memang benar; keduanya berhenti di *lokasi*, tidak pernah menyentuh *isi*.
  Hasilnya: **divergensi ini tidak muncul di satu artefak pun.** Ia hanya ketahuan karena
  seorang analis kebetulan membuka dua diff berdampingan.
- **Bukti penguat (case kedua — dan di sini divergensinya FUNGSIONAL, bukan non-fungsional) —
  django-12286** (temuan bot-01, 2026-07-20). Bukti:
  `f-dev--django__django-12286--r1/files/fix.diff` vs `cases/gold/django__django-12286/gold.patch`,
  plus `test_patch` di `cases/gold/django__django-12286/swebench_spec.json`.
  - **Gold membuang logikanya dan mendelegasikan ke sumber kebenaran runtime:** ia mengimpor
    `get_supported_language_variant` lalu mengganti seluruh uji keanggotaan dengan
    `try: get_supported_language_variant(settings.LANGUAGE_CODE) / except LookupError:
    return [E004]`. Fungsi itu menelusuri **bertahap** (`zh-hans-x` → `zh-hans` → `zh`) dan
    adalah fungsi yang **sama** dengan yang dipakai runtime i18n untuk memilih bahasa.
  - **Model mempertahankan uji keanggotaan lalu menempelkan cabang tambahan:**
    `if '-' in language_code: base = language_code.split('-', 1)[0]; if base in
    available_tags: return []`. Ini fallback **satu tingkat, ke komponen pertama saja**,
    ditulis ad hoc di lapisan checks.
  - **Pernyataan yang tepat soal konsekuensinya (dan yang TIDAK boleh dilebihkan):** untuk
    setiap `LANGUAGE_CODE` yang **bahasa dasarnya** terdaftar di `LANGUAGES`, kedua patch
    setuju — **termasuk kode tiga komponen** `ca-ES-valencia` yang memang ada di F2P resmi
    `test_valid_variant_consistent_language_settings`, karena `LANGUAGES` di test itu memuat
    `('ca', 'Catalan')` sehingga `split('-', 1)[0]` kebetulan mendarat benar. Divergensinya
    muncul ketika yang terdaftar adalah **varian antara, bukan bahasa dasar**: dengan
    `LANGUAGES=[('zh-hans', ...)]` dan `LANGUAGE_CODE='zh-hans-x'`, gold **menerima**
    (menelusuri ke `zh-hans`), model **menolak** dengan E004 (`split('-', 1)[0]` = `zh`,
    tidak terdaftar). **Tidak ada satu pun test resmi yang membangun konfigurasi itu**,
    sehingga F2P 1/1 dan P2P 7/7 hijau dan `resolved=true`.
  - **Divergensi kedua, struktural dan sama sekali tak terukur:** model **menduplikasi
    resolusi bahasa** di lapisan checks alih-alih memakai sumber kebenaran yang dipakai
    runtime. Konsekuensinya check dan runtime bisa **divergen** begitu salah satu berubah —
    yaitu persis pelanggaran "satu himpunan, satu sumber kebenaran" yang di katalog ini
    sudah jadi tema berulang (LV-03, LV-09). Gold justru memilih fix yang **menghapus**
    duplikasi itu; model memilih fix yang **menambahnya**.
  - **Instrumentasi (a) menangkapnya dengan tepat dan murah:** himpunan identifier di baris
    `+` gold memuat `get_supported_language_variant` dan `LookupError`; di baris `+` model
    tidak ada satu pun dari keduanya. Jadi `gold_only_symbols = {get_supported_language_variant,
    LookupError}` adalah **ringkasan akurat dari seluruh perbedaan semantiknya**, dan ia
    keluar dari perbandingan tekstual belaka — tanpa perlu tahu apa pun soal i18n.
  - **Kenapa case ini lebih kuat daripada case asalnya:** di 12915 yang hilang adalah properti
    **non-fungsional** (blocking di event loop) yang masih bisa didebat apakah "salah"; di
    12286 yang hilang adalah **perilaku fungsional** yang gold jelas punya dan patch model
    jelas tidak, dan bisa dibuktikan dengan **satu contoh input**. Dan sekali lagi
    `gold_eval.json` fase FIX mencatat `file_match: true` + `line_overlap: true` — dua-duanya
    hijau, dua-duanya benar, dua-duanya **buta pada isi hunk**.
- **Bukti penguat (case ketiga — divergensinya nyaris nol, dan justru itu yang berguna:
  ia menunjukkan BATAS instrumentasi (a)) — django-11039** (temuan bot-01, 2026-07-20).
  Bukti: `f-dev--django__django-11039--r1/files/fix.diff` vs
  `cases/gold/django__django-11039/gold.patch`.
  - **Baris kodenya identik.** Kedua patch menulis
    `self.output_transaction = migration.atomic and connection.features.can_rollback_ddl`
    di file dan titik sisip yang sama. `gold_eval.json`: `file_match: true`,
    `line_overlap: true`. Ini **divergensi fungsional nol** — case pertama di korpus di mana
    itu bisa dikatakan.
  - **Yang berbeda hanya komentarnya, dan komentarnya kini berbohong.** Gold **memperbarui**
    komentar di atas baris itu: `# Show begin/end around output only for atomic migrations`
    → `# Show begin/end around output for atomic migrations, if the database supports
    transactional DDL.` Model **membiarkan komentar lama**, sehingga file hasilnya memuat
    komentar yang menyatakan syaratnya hanya `atomic` tepat di atas kode yang syaratnya
    `atomic AND can_rollback_ddl`.
  - **Kenapa ini layak dicatat di entri ini dan bukan diabaikan:** instrumentasi (a)
    sebagaimana diusulkan membandingkan **himpunan identifier di baris `+`**. Di sini
    `gold_only_symbols` = himpunan kosong dan `model_only_symbols` = himpunan kosong —
    (a) akan melaporkan "setara", dan **itu benar untuk perilaku runtime tetapi meleset untuk
    isi hunk**. Jadi 11039 adalah **kasus batas yang menandai apa yang (a) tidak lihat:
    komentar, docstring, dan seluruh perubahan non-identifier.** Tidak mengubah usulan (a) —
    memperbaikinya agar membaca komentar akan menukar detektor murah-dan-tepat dengan
    detektor berisik — tetapi wajib ditulis supaya `gold_only_symbols: []` kelak tidak
    dibaca sebagai "patch setara gold".
  - **Kalibrasi kepentingan, supaya tidak dilebihkan:** komentar basi bukan regresi dan tidak
    terukur test mana pun; ongkos run-nya nol (full green, 7 turn di FIX). Nilainya murni
    sebagai **batas detektor**, bukan sebagai kerugian.
- **Bukti penguat (case keempat — dan yang PERTAMA di mana sinyal yang sudah dipegang harness
  benar-benar akan menandai sebuah lulus-palsu) — django-13658** (temuan bot-01, 2026-07-20).
  Bukti: `f-dev--django__django-13658--r1/files/fix.diff` vs
  `cases/gold/django__django-13658/gold.patch`; `gold_eval.json` + `swebench_eval.json` run
  yang sama; `test_patch` di `cases/gold/django__django-13658/swebench_spec.json`.
  - **Kedua patch tidak berada di file yang sama.** Gold menyentuh
    `django/core/management/__init__.py` (menambah `prog=self.prog_name` pada `CommandParser`
    di `execute()`); model menyentuh `django/core/management/base.py` (menambah default
    `kwargs["prog"] = sys.argv[0] if (sys.argv and sys.argv[0] is not None) else "django-admin"`
    di `CommandParser.__init__`). `gold_eval.json`: **`file_match: false`**,
    `line_overlap: null`. `swebench_eval.json`: **`resolved: true`**, F2P 1/1
    (`test_program_name_from_argv`), P2P **181/181**.
  - **Divergensi perilakunya nyata dan terukur** (diverifikasi bot-01 dengan menjalankan
    A/B base vs model vs gold di dalam image case ini, meng-instrumentasi `prog` dari setiap
    `CommandParser` yang dibuat). Dengan argv pemanggil `['my_prog','help','shell']`:
    - `sys.argv[0]` berbeda dari argv pemanggil → parser top-level: **gold `'my_prog'`,
      model `'/usr/local/bin/other_prog'`**.
    - `sys.argv[0] is None` (kondisi issue) → **gold `'my_prog'`, model `'django-admin'`**.
    Yaitu: gold menurunkan program name dari **argv pemanggil**, model dari **`sys.argv`
    dengan konstanta cadangan** — persis perilaku yang judul test resminya menyatakan sudah
    diperbaiki.
  - **Regresi diam-diam ke call site kedua, terverifikasi eksekusi.** Hanya ada **dua**
    pemanggil `CommandParser` tanpa `prog` di seluruh `django/`:
    `__init__.py:347` (titik gold) dan `utils.py:118`
    (`get_command_line_option`) — `base.py:280` mengoper `prog` eksplisit
    (`grep -rn 'CommandParser(' /testbed/django/`). Karena patch model bekerja di
    **konstruktor**, ia ikut mengubah `utils.py:118`: default argparse
    `os.path.basename(sys.argv[0])` menjadi `sys.argv[0]` **utuh berikut path**. Terukur:
    dengan `sys.argv[0] = '/usr/local/bin/my_prog'`, prog parser itu **base `'my_prog'` →
    model `'/usr/local/bin/my_prog'`**, sedangkan **gold membiarkannya `'my_prog'`**. Jadi
    berbeda dari 12915 dan 12286, di sini patch model **mengubah perilaku di luar situs yang
    diperbaiki** — dan **181 P2P tidak melihatnya**.
  - **Kenapa case ini lebih kuat daripada tiga case sebelumnya, dan ini kontribusi utamanya:**
    di 12915, 12286, dan 11039 divergensi hanya bisa ditemukan dengan **membuka dua diff
    berdampingan** — persis keluhan yang melahirkan entri ini. Di 13658, harness **sudah
    menuliskan vonisnya sendiri ke disk**: `file_match: false` ada di `gold_eval.json` sejak
    detik run itu selesai. Yang hilang bukan datanya, melainkan **konsumennya** — dashboard
    menghitung AND(L1, L2) dan `fix_gold_eval` berstatus advisory, sehingga satu-satunya
    run di korpus yang patch-nya mendarat di file lain sama sekali terbaca **hijau sempurna**
    di papan skor.
  - **Konsekuensi konkret untuk usulan (a) — sub-item berongkos nol yang mendahuluinya.**
    (a) sebagaimana ditulis menuntut pekerjaan baru (bandingkan himpunan identifier di baris
    `+`). 13658 menunjukkan ada **lapis yang lebih murah lagi dan sudah selesai dikerjakan**:
    **munculkan `resolved` dan `file_match` berdampingan**. Usul konkret: state dashboard baru
    — sejajar dengan ANOMALY yang sudah ada untuk *"product FAIL tapi `resolved=true`"* — untuk
    kebalikannya, **`resolved=true` tetapi situs patch berbeda dari gold**. Nol komputasi baru,
    nol perubahan kontrak, nol sentuhan ke jalur vonis; ia hanya berhenti menyembunyikan dua
    field yang sudah tertulis. Frekuensinya di korpus: **1 dari 12 run `f-dev` yang punya
    `swebench_eval.json` DAN `gold_eval.json`** (dan **1 dari 8** yang `resolved=true`) —
    lihat Tabel D di section frekuensi.
- **Bukti penguat (case kelima — batas KEDUA instrumentasi (a), kali ini sisi false positive) —
  django-11179** (temuan bot-01, 2026-07-20). Bukti:
  `f-dev--django__django-11179--r1/files/fix.diff` vs `cases/gold/django__django-11179/gold.patch`.
  - `gold_eval.json`: `file_match: true`, `line_overlap: true`, `resolved: true`,
    F2P 1/1, P2P 40/40. Titik sisip identik, satu baris.
  - **Barisnya berbeda secara tekstual tetapi setara secara semantik.** Gold:
    `setattr(instance, model._meta.pk.attname, None)`. Model: `instance.pk = None`.
    Kesetaraannya **diverifikasi bot-01 di dalam image case ini**, bukan disimpulkan:
    `django/db/models/base.py:571` pada base commit case ini berbunyi persis
    `def _set_pk_val(self, value): return setattr(self, self._meta.pk.attname, value)`,
    dengan `pk = property(_get_pk_val, _set_pk_val)` di baris 574. Jadi bentuk model
    **men-desugar tepat menjadi bentuk gold**.
  - **Kenapa ini wajib ditulis di entri ini:** instrumentasi (a) membandingkan **himpunan
    identifier di baris `+`**. Di sini `gold_only_symbols` = `{setattr, model, _meta, attname}`
    dan `model_only_symbols` = `{}` — yaitu **(a) akan melaporkan divergensi untuk patch yang
    sepenuhnya setara.** 11039 sudah menandai batas (a) di sisi **false negative**
    (`gold_only_symbols` kosong padahal isi hunk beda); 11179 menandai batas yang berlawanan.
    Dua-duanya perlu, dan dua-duanya menuju kesimpulan desain yang sama: **`gold_only_symbols`
    adalah pemicu untuk DILIHAT MANUSIA, bukan predikat kesetaraan** — jangan sekali-kali
    dibaca sebagai vonis ke arah mana pun. Ini memperkuat, bukan melemahkan, keputusan entri
    ini bahwa (a) hidup sebagai instrumentasi non-blocking.
  - **Catatan kalibrasi versi, karena ia bisa menjebak pembaca kemudian:** kesetaraan itu
    **spesifik untuk commit ini**. Di Django yang lebih baru `_set_pk_val` menambahkan loop
    atas `self._meta.parents` (diverifikasi ada di image `django__django-13658`), sehingga
    `instance.pk = None` di sana melakukan **lebih** daripada `setattr(...)` untuk model
    multi-table inheritance. Jadi "setara" di sini adalah pernyataan tentang **satu commit**,
    dan itu sendiri argumen kenapa perbandingan tekstual tidak boleh dipromosikan jadi vonis.
- **Diagnosa — dan bagian terpentingnya adalah memisahkan dua hal yang mudah tercampur:**
  1. **Batas metodologi (BUKAN akar-harness, BUKAN akar-model).** Bahwa L2 tidak menangkap
     regresi non-fungsional adalah sifat dari *definisi ground truth* yang kita pakai:
     `resolved=true` berarti "test resmi SWE-bench hijau", tidak pernah berarti "patch
     setara gold". Test suite itu milik benchmark, bukan milik kita; memperbaikinya berarti
     berhenti mengukur SWE-bench. Jadi ini bukan cacat yang bisa dilever — ini **plafon
     dari alat ukurnya**, dan yang bisa kita lakukan hanyalah berhenti membacanya lebih
     jauh dari yang ia klaim. Dicatat sebagai batas, lihat Catatan penutup #1.
  2. **Akar-harness yang sempit dan nyata (inilah yang dilever entri ini):** di realm eval,
     harness **sudah memegang gold patch** dan sudah membandingkannya dengan patch model —
     tetapi perbandingannya berhenti di himpunan file dan rentang baris. Tidak ada satu
     konsumen pun untuk pertanyaan "apa yang ada di hunk gold dan tidak ada di hunk model".
     Padahal di case ini pertanyaan itu dijawab oleh satu nama simbol: `sync_to_async`.
  3. *Akar-model:* ada, tapi tipis dan tidak boleh dibesarkan. Model tidak diberi tahu
     bahwa jalur ini async-sensitif, dan yardstick satu-satunya yang ia punya (repro r2)
     memang tidak bisa membedakan kedua bentuk (lihat LV-01, bukti penguat 12915).
     Menyalahkan penalaran model untuk sesuatu yang tak satu pun alat ukur kita tanyakan
     adalah cara termahal untuk belajar (aturan main #6).
- **Usulan lever — instrumentasi, non-blocking, seluruhnya di realm eval:**
  - (a) **Flag divergensi isi di `gold_eval.json`.** Setelah L2 selesai, bandingkan
    himpunan identifier yang muncul di baris `+` gold dengan yang muncul di baris `+`
    patch model, lalu catat `gold_only_symbols` (di 12915 isinya `sync_to_async`,
    `asgiref.sync`) dan `model_only_symbols`. **Tidak menggugurkan apa pun** — ia hanya
    membuat "hijau tapi tidak setara" jadi terbaca dari artefak. Ini pola yang persis sama
    dengan LV-13(b): mengubah detektor gratis yang sudah setengah terpasang menjadi detektor
    yang punya konsumen. Bedanya objek: LV-13(b) mencocokkan *prosa model* dengan kode;
    entri ini mencocokkan *patch model* dengan *gold*, post-hoc. Karena itu dicatat sebagai
    lever tersendiri, bukan bukti penguat LV-13.
  - (b) **Lint async advisory** atas file yang disentuh patch: tandai pemanggilan sinkron
    tanpa `await`/`sync_to_async` di dalam `async def` yang baru ditambahkan. Dinilai
    **lebih rendah** dari (a) dengan sengaja: cakupannya cuma satu domain (async), rawan
    false positive (banyak panggilan sinkron di `async def` memang sah), dan ia menjawab
    gejala 12915 secara spesifik alih-alih kelasnya. (a) generik dan tidak butuh tahu apa
    pun soal async.
  - **Batas yang wajib dijaga:** keduanya hanya boleh hidup **setelah** vonis L2, dan
    hasilnya **tidak boleh** kembali ke model atau ke fase mana pun. Begitu perbandingan
    gold dipakai sebagai umpan balik, kita berhenti mengukur dan mulai membocorkan.
- **Status:** BELUM DITERAPKAN.
  - *Tambahan bertanggal 2026-07-20 (bot-01):* alasan **"n=1"** yang dipakai di baris
    Prioritas di bawah **sudah tidak berlaku** — django-12286 menjadikannya **n=2**, dan
    divergensi di case kedua itu **fungsional**, bukan non-fungsional. Ongkos run-nya tetap
    nol (full green, 7 turn di FIX), jadi vonis "instrumentasi, bukan gate" **tidak berubah**;
    yang berubah hanya argumen "tunggu case berikutnya", yang kini sudah terjawab.
    Rekomendasi konkret: naikkan **(a)** menjadi **prioritas instrumentasi teratas bersama
    LV-13(b)** dan pasang keduanya sekaligus — keduanya menulis flag ke `gold_eval.json`,
    keduanya post-hoc, dan tak satu pun menyentuh jalur vonis atau kembali ke model.
- **Prioritas:** **rendah sebagai lever, sedang sebagai instrumentasi** — sama persis dengan
  posisi LV-12 dan LV-13(b), dan alasannya sama: **n=1**, ongkos run-nya **nol** (full green,
  2 turn di FIX, tidak ada churn yang bisa dihemat), dan ia tidak memperbaiki hasil satu run
  pun. Yang membuatnya tetap layak dicatat sekarang bukan frekuensi melainkan (i) divergensinya
  **definitif dan bisa diverifikasi mesin** dari gold patch — bukan soal selera, sama seperti
  alasan LV-13 diterima di n=1; dan (ii) tanpa flag ini kita **tidak punya cara tahu berapa
  banyak kolom hijau lain yang berdiri di atas patch yang tidak setara** — jadi biaya
  sebenarnya bukan di run ini, melainkan di ketidaktahuan yang menumpuk lintas papan skor.
- **Catatan kejujuran (dua hal yang TIDAK boleh diklaim):**
  1. Ini bukan "regresi". Terhadap base, patch model adalah perbaikan — sebelumnya
     `ASGIStaticFilesHandler` tidak berfungsi sama sekali. Yang benar dikatakan: patch model
     **kehilangan properti non-fungsional yang dimiliki gold**, bukan merusak sesuatu yang
     tadinya baik.
  2. Ada kemungkinan divergensinya **tidak murni non-fungsional** — Django menandai operasi
     tertentu `async_unsafe`, sehingga jalur `response_for_exception` yang menyentuh operasi
     semacam itu akan melempar di dunia model tapi tidak di dunia gold. **Ini hipotesis yang
     TIDAK diverifikasi di run ini** (tidak ada artefak yang menyentuhnya, dan F2P 404 lolos),
     jadi ditulis sebagai catatan, bukan sebagai bukti. Kalau ada yang mau menaikkan prioritas
     entri ini, verifikasi itulah pekerjaannya.

---

## Catatan penutup autopsi 12915 (bot-01, 2026-07-20)

1. **Batas metodologi, dinyatakan eksplisit supaya tidak terus-menerus ditemukan ulang:**
   `resolved=true` adalah pernyataan tentang **test suite resmi SWE-bench**, bukan tentang
   kesetaraan dengan gold. 12915 adalah bukti terbersih untuk itu di korpus ini, karena di
   sini semuanya hijau — F2P 3/3, P2P 8/8, `file_match`, `line_overlap` — dan patch-nya
   tetap berbeda dari gold pada properti yang keberadaan `sync_to_async` di gold justru
   ada untuk menjamin. **Ini plafon alat ukur, bukan cacat yang bisa diperbaiki:** test
   suite-nya milik benchmark. Konsekuensi praktis: L2 adalah yardstick tertinggi kita dan
   tetap begitu, tapi ia **lantai kepercayaan, bukan langit-langitnya**. Ini alasan keempat
   (setelah 11099, 14017, 13230) untuk tidak membaca kolom hijau sebagai validasi — dan yang
   pertama di mana kelonggarannya datang dari alat ukur **resmi**, bukan dari repro buatan
   model. Yang bisa dilever hanyalah kemampuan **melihat** divergensinya (LV-14a).
2. **Vonis atas pertanyaan "kelas baru atau varian LV-01": DUA-DUANYA BUKAN, dan pemisahannya
   penting.** Mekanisme abstraknya memang sekeluarga dengan LV-01 ("predikat lebih sempit
   daripada kontrak"), tapi menggabungkannya akan merusak LV-01: usulan lever LV-01 adalah
   *perketat repro*, dan tidak ada versi dari usulan itu yang bisa menjangkau test suite
   SWE-bench. Sumber kelonggarannya beda, dan yang lebih menentukan: **konsekuensinya beda.**
   Di LV-01, yardstick longgar meloloskan fix salah yang **kemudian ketahuan di L2** (13660,
   14017) — sistemnya masih punya mata. Di 12915, tidak ada lapis berikutnya yang bisa
   melihat. Karena itu bagian yang tak bisa diperbaiki dicatat sebagai **batas metodologi**
   (butir 1 di atas), dan hanya bagian yang benar-benar kita miliki — instrumentasi
   perbandingan patch-vs-gold di realm eval — yang jadi entri (LV-14).
3. **12915 adalah A/B terbaik yang dimiliki korpus ini untuk LV-05.** Satu case, dua run,
   script yang praktis sama, vonis judge berlawanan, dan selisihnya 26 turn gagal vs 10 turn
   lolos. Sebelumnya judge selalu menolak di **semua** run sebuah case, sehingga masih bisa
   dibaca sebagai "aturannya menjerat bentuk ini". Sekarang terukur bahwa **judge tidak
   deterministik atas masukan yang praktis identik**, dan lemparan koin itu menentukan
   verdict fase. Ini menaikkan bobot LV-05 dari "aturan terlalu luas" jadi "presedensi vonis
   diberikan ke komponen yang tidak stabil". LV-05(b) sebagaimana tertulis akan menyelamatkan
   run ini (kategori `mechanics` + exec-pair sudah hijau) — case pertama di mana (b) tepat
   sasaran.
4. **Keterpaparan LV-09 di case ini murni kebetulan, dan itu temuan tersendiri.** r1 memakai
   `pipe_runtime`, r2 tidak; yang lolos gate kebetulan r2, sehingga fase FIX 12915 selesai
   dalam 2 turn dan bukan meledak seperti 11910. Kalau r1 yang lolos, repro beku akan diawali
   `from pipe_runtime import App` di container FIX yang tidak punya modul itu. Jadi papan skor
   yang kita baca sebagian ditentukan oleh **gaya repro mana yang kebetulan lolos judge** —
   dan itu memperkuat dua lever sekaligus (LV-05 di hulu, LV-09 di hilir).
5. **Kelas kegagalan REPRODUCE r1 seluruhnya sudah tercatat.** 12 retry, nol mekanisme baru:
   1 judge (LV-05) yang memicu 8 retry berikutnya, 4 `app failed to become ready` (LV-06),
   4 `REPRO_STATUS: ERROR` (LV-10b), checkpoint dibuang selama 16 turn (LV-08). Bahwa autopsi
   ketiga berturut-turut tidak menemukan mekanisme kegagalan REPRODUCE yang baru adalah
   sinyal yang layak dibaca: katalog ini mulai **jenuh** di fase REPRODUCE, dan nilai marjinal
   dari autopsi berikutnya kemungkinan lebih rendah daripada nilai memasang LV-05/LV-09/LV-10.
6. **Kandidat lever yang SENGAJA TIDAK dijadikan entri — "model menargetkan Python modern,
   testbed Python 3.6".** `AttributeError: module 'asyncio' has no attribute 'run'` muncul di
   **kedua** run 12915 (r1 retry ke-2, r2 retry ke-1) — 2 kejadian, 2 run, **1 turn masing-masing**,
   dan model langsung memperbaikinya sendiri jadi `get_event_loop().run_until_complete(...)`.
   Bentuk mekanisnya jelas dan murah (sebut versi interpreter container di prompt pembuka,
   atau sediakan helper). **Tapi buktinya tipis dan ongkosnya kecil** — persis kategori yang
   sama dengan kandidat "helper bootstrap framework" di catatan penutup 13230, dan alasan
   penolakannya sama: jangan bikin lever dari 2 kejadian berongkos 1 turn. Dicatat di sini
   supaya tidak hilang; naikkan jadi entri kalau muncul lagi di case ketiga, atau kalau
   sekali waktu ia yang membunuh sebuah run alih-alih memakan satu turn.
7. **Akar-model vs akar-harness untuk case ini, jujur.** Bagian model: repro r1 memakai
   `ROOT_URLCONF='django.conf.urls'` (modul tanpa `urlpatterns`) dan tidak pernah membuat
   `test.txt` — dua kecerobohan environment yang **asli miliknya**, dan itulah yang membuat
   run gold-patched jatuh ke `ImproperlyConfigured`. Bagian harness: kecerobohan itu tidak
   perlu berakhir sebagai verdict `wrong-logic` dengan diagnosis yang **salah secara faktual**
   (`no REPRO_STATUS token` atas output yang jelas-jelas memuat `REPRO_STATUS: ERROR`), dan
   16 dari 26 turn yang dipakai untuk sampai ke sana adalah anak penolakan judge. Pembagian
   yang paling defensibel: **penyebab langsung kegagalan flip r1 adalah akar-model; penyebab
   run itu ada di jalur tersebut sama sekali, dan penyebab kita salah mendiagnosisnya,
   adalah akar-harness.**

---

## Autopsi django-12286 — full green yang membayar penuh di tiga lever sekaligus
## (bot-01, 2026-07-20)

**Korpus:** `artifacts/r-dev/r-dev--django__django-12286--r1` (qualified),
`artifacts/l-dev/l-dev--django__django-12286--r1` (qualified),
`artifacts/f-dev/f-dev--django__django-12286--r1` (menang attempt 1).
Gold: `cases/gold/django__django-12286/gold.patch`. Bug:
`check_language_settings_consistent` menolak `LANGUAGE_CODE` sublanguage (`de-at`) padahal
bahasa dasarnya (`de`) ada di `LANGUAGES`.

**Hasil (terverifikasi ulang dari artefak):** FULL GREEN, tanpa satu pun rerun gagal.
`f-dev/.../swebench_eval.json` → `resolved=true`, `patch_successfully_applied=true`,
F2P **1/1** (`test_valid_variant_consistent_language_settings`), P2P **7/7**,
`f2p_failed=[]`, `p2p_failed=[]`, `rerun=1`. Ketiga fase `pass_l1=true`.

**Angka biaya per fase:**

- REPRODUCE: **19 turn, 14 attempt internal, 14 event `retry`**, `console.log` 1.744 baris.
- LOCALIZE: **2 turn**, 0 retry, console 259 baris. `qualified=true`, `file_match=true`,
  **`line_overlap=false`** (`pointed_lines: [11, 22]`, gold di ~56–63).
- FIX: **7 turn, 1 attempt, `win`/`flip`**, 12 event retry, console 1.155 baris.

**Pembagian 14 retry REPRODUCE:**

- **1× kecerobohan koding model** (`settings.ModuleNotFoundError` dipakai sebagai nilai
  `ROOT_URLCONF` → `ImproperlyConfigured`). Akar-model, 1 turn, langsung diperbaiki sendiri.
- **6× `exited 0 ... last output line: REPRO_STATUS: PASS`** di t2–t8 — repro belum berhasil
  memicu E004 (model mula-mula memakai `run_checks()`, yang tidak menjalankan check
  translation; baru `execute_from_command_line(['manage.py','check'])` yang memicunya).
  Akar-model, dan **gate bekerja persis sebagaimana mestinya** di sini: ia menolak repro
  yang tidak mereproduksi.
- **1× penolakan judge** di t10 atas script yang exec-pair-nya **sudah hijau** (LV-05).
- **6× akibat langsung penolakan itu** di t11–t19: 1 halusinasi API `App` (`env=`),
  1 `FileNotFoundError`, **2× `app failed to become ready`** (LV-06), 2× `REPRO_STATUS: PASS`.

Jadi: **nol retry yang sebabnya "salah paham bug"** — konsisten dengan 13660, 13230, 12915.
Dan **7 dari 14 retry (50%) plus 9 dari 19 turn (47%) adalah anak langsung satu panggilan
judge**, di case yang bug-nya dipahami model dengan benar sejak `repro.md` di t9.

**Rantai sebab yang membuat case ini layak dibaca ulang — ini kontribusi utamanya:**

> **LV-05 → LV-09 → LV-11, dalam satu case, terekam lengkap.**
> Judge menolak repro in-process yang sudah terbukti hijau, mengutip aturan `app-runtime` +
> `pipe_runtime` (kategori `mechanics`). Model patuh dan menulis ulang repro-nya di atas
> `App`. Repro itulah yang dibekukan — dengan `from pipe_runtime import App` di baris 4.
> Di fase FIX, container kerja tidak punya modul itu (LV-09): **5 traceback
> `ModuleNotFoundError`, 5 dari 12 retry, 4 dari 7 turn hangus**. Kehilangan alat ukur,
> model membangun penggantinya — `verify_fix.py`, rekonstruksi `repro_project/`, dan
> akhirnya **menimpa `/testbed/.pipe/repro.py`** lalu mendeklarasikan DONE di atas PASS dari
> file yang ia tulis sendiri (LV-11).

Di Catatan penutup 12915 butir 4, rantai ini masih ditulis sebagai *kemungkinan* — "kalau r1
yang lolos gate, fase FIX akan mendarat persis di kelas 11910". Di 12286 lemparan koinnya
mendarat di sisi itu. Yang membedakannya dari 11910 dan membuatnya tetap hijau adalah hal
yang membosankan: **ruang fix-nya sempit** (satu fungsi, satu file, sudah ditunjuk LOCALIZE),
sehingga patch yang menang selesai ditulis di **t3** dan empat turn sisanya hanyalah model
bergulat dengan alat ukurnya. Ini alasan **kelima** untuk tidak membaca kolom hijau sebagai
validasi (setelah 11099, 14017, 13230, 12915).

**Ke mana temuan run ini masuk (semuanya bukti penguat / klarifikasi — nol entri baru):**

- LV-01 — bukti penguat kelima: repro terlonggar di korpus (satu substring, semua mode gagal
  jatuh ke PASS, nol kontrol positif, `return []` tanpa syarat akan lolos).
- LV-05 — bukti penguat keempat: judge `mechanics` menolak exec-pair yang sudah hijau;
  ongkos 9 turn / 6 retry; case kedua di mana LV-05(b) tepat sasaran.
- LV-06 — bukti penguat ketiga: halusinasi API ke-6 (`env=`) + 2× one-shot ready-line
  (kelas itu kini 3 case, 8 kejadian).
- LV-07 — titik data kedua: `PASS_OBSERVABLE: translation.E004` non-kanonik diterima driver
  (kali ini tanpa kerugian).
- LV-08 — bukti penguat keempat: checkpoint in-process dibuang, 9 turn, tak pernah kembali;
  4 dari 4 case menunjukkan checkpoint lebih baik daripada penggantinya.
- LV-09 — bukti penguat kelima (angka lengkap) **+ klarifikasi bertanggal** yang mengoreksi
  overclaim analis sebelumnya.
- LV-10 — bukti penguat untuk (a) dan (b), termasuk catatan bahwa keselamatan di case ini
  bergantung pada **di baris berapa** dunia itu pecah.
- LV-11 — bukti penguat kedua (yardstick beku ditimpa penuh) **+ klarifikasi bertanggal**
  yang menurunkan klaim "melubangi integritas gate" dan menaikkan LV-10(a).
- LV-13 — titik data kedua untuk (b): `check_language_code` / `language_codes` dikarang,
  rentang meleset ~40 baris, tetap `qualified`, tetap tidak merugikan.
- LV-14 — bukti penguat kedua, dan **lebih kuat dari case asalnya**: divergensi fungsional
  yang bisa dibuktikan dengan satu contoh input, terangkum tepat sebagai
  `gold_only_symbols = {get_supported_language_variant, LookupError}`.

---

## Catatan penutup autopsi 12286 (bot-01, 2026-07-20)

1. **Koreksi yang paling penting dari batch ini: bedakan "loop iterasi rusak" dari "vonis
   tidak valid".** Pembacaan sebelumnya atas case ini menyimpulkan bahwa karena LV-09, agen
   FIX memvalidasi diri dengan script buatannya sendiri sehingga **validitas fase FIX
   melemah**. Itu **overclaim, dan salah di kode**. `run_fix_gemma.py:30,303–305` dan
   `run_fix_gates.py:23,88` memanggil `evaluate_patch_in_fresh_world` yang **sama** dengan
   argumen `args.input_repro_files` yang **sama** — direktori artefak **beku** fase R di
   host — dan `repro_sandbox_runner.py:25–37` me-mount direktori itu `/pipe-in:ro` lalu
   menyalin `repro.py` **dan** `pipe_runtime.py` ke container segar. DONE hanya diterima
   ketika **repro beku lolos di dunia segar yang lengkap**; pre-check dan gate memakai
   **standar tunggal yang sama**. Vonis `flip` SAH, `resolved=true` sah. Yang rusak adalah
   **alat ukur yang dipegang model selama ia bekerja** — nyata, mahal, dan layak dilever,
   tetapi bukan kebocoran gate. Klarifikasi bertanggal ditulis di Status LV-09 dan LV-11.
   Pelajaran metodologisnya melampaui case ini: **sebelum menyatakan sebuah vonis tidak
   valid, telusuri jalur kode yang menghasilkan vonis itu, bukan jalur yang dilihat model.**
2. **Vonis atas "model mengganti yardstick-nya sendiri saat yardstick rusak": TERCAKUP
   LV-11, bukan mekanisme baru — tetapi ia MEMPERBAIKI desain lever-nya.** Mekanismenya
   identik dengan 11910 ("beku" adalah konvensi tanpa mesin yang memeriksanya); yang berbeda
   hanya bentuk pelanggarannya — **substitusi, bukan mutasi**, plus dua yardstick tandingan
   di luar `/testbed/.pipe`. Konsekuensi desain yang nyata: pagar `chmod 0444` + tolak aksi
   `file` ke `/testbed/.pipe` **tidak menutup kelas ini** (model masih bisa mengukur diri
   dengan `verify_fix.py`), dan pagar berbasis diff git **buta secara struktural** terhadap
   `/testbed/.pipe` karena direktori itu tidak ter-track — dibuktikan langsung oleh
   `git checkout -- /testbed/.pipe/repro.py` yang gagal dengan `did not match any file(s)
   known to git`. Yang tersisa sebagai penutup kelas adalah **verifikasi hash sebelum
   menerima DONE**. Per aturan main #4, ini ditulis sebagai bukti penguat di LV-11, bukan
   entri baru.
3. **Nol entri baru, dan itu sendiri temuan — sinyal jenuh kini terkonfirmasi di fase FIX,
   bukan cuma REPRODUCE.** Catatan penutup 12915 butir 5 mencatat tiga autopsi berturut-turut
   tanpa mekanisme REPRODUCE yang baru. 12286 adalah yang keempat, dan ia memperluas sinyal
   itu: fase FIX-nya pun **tidak melahirkan satu mekanisme baru** — seluruh 4 turn hangusnya
   dijelaskan LV-09, dan seluruh perilaku tamperingnya dijelaskan LV-11. Pembacaan yang
   paling jujur: **nilai marjinal autopsi berikutnya sekarang lebih rendah daripada nilai
   memasang LV-09 + LV-10(a) + LV-05(b).** Urutan yang tetap disarankan tidak berubah dari
   catatan penutup 11910/11099 butir 5, hanya bertambah satu alasan.
4. **Kandidat lever yang SENGAJA TIDAK dijadikan entri — "pesan penolakan driver menyuruh
   model melakukan yang mustahil".** Pre-check DONE menolak dengan kalimat *"Not done yet:
   run `python /testbed/.pipe/repro.py` and get `REPRO_STATUS: PASS` in its output first"*
   (4× di run ini), padahal di container itu perintah tersebut **tidak akan pernah** bisa
   menghasilkan PASS secara jujur — modulnya hilang. Sementara itu kriteria penerimaan yang
   sesungguhnya berada di dunia lain (fresh-world pair atas repro beku, lihat butir 1).
   Jadi ada divergensi nyata antara **prasyarat yang dikomunikasikan ke model** dan
   **kriteria yang dipakai driver**, dan ketika yardstick container mati, prasyarat yang
   dikomunikasikan itu **secara harfiah hanya bisa dipenuhi dengan mengubah yardstick** —
   yang persis dilakukan model di t5, lengkap dengan komentarnya sendiri *"so that it can
   print 'REPRO_STATUS: PASS' as required"*. Menggoda untuk dijadikan entri, tetapi
   **buktinya tipis dan posisinya orde kedua**: n=1, seluruhnya hilir dari LV-09, dan
   LV-10(a) akan membatalkan attempt sebelum pesan itu sempat dikirim sekali pun. Dicatat
   di sini supaya tidak hilang. **Syarat menaikkannya jadi entri:** (i) muncul lagi di case
   lain **setelah** LV-09 dan LV-10(a) terpasang — artinya divergensi pesan-vs-kriteria itu
   berdiri sendiri, bukan gejala yardstick mati; atau (ii) ditemukan satu run di mana model
   memenuhi pesan itu dengan tampering **dan** repro beku di dunia segar kebetulan juga
   lolos karena longgar (LV-01), sehingga tampering ikut menentukan hasil.
5. **Akar-model vs akar-harness untuk case ini, jujur.** *Bagian model:* (i) 6 retry awal
   karena `run_checks()` tidak menjalankan check translation — kekeliruan asli, walau
   diperbaiki sendiri; (ii) `evidence` LOCALIZE yang mengarang nama fungsi dan variabel
   (LV-13b); (iii) repro dengan cabang gagal-mengamati yang jatuh ke PASS dan tanpa kontrol
   positif (LV-01/LV-10b); (iv) patch yang menduplikasi resolusi bahasa secara ad hoc alih-alih
   mendelegasikan seperti gold (LV-14) — meski soal (iv) perlu dicatat adil bahwa **tak satu
   pun alat ukur kita menanyakannya**, jadi menyalahkan penalaran model di sini adalah cara
   termahal untuk belajar (aturan main #6). *Bagian harness:* penolakan judge yang mengubah
   kelas repro (LV-05), dependency yang tidak ikut dikirim (LV-09), tidak adanya pre-flight
   (LV-10a), dan tidak adanya pagar atas yardstick beku (LV-11). **Pembagian yang paling
   defensibel:** semua yang menentukan **hasil** case ini adalah akar-model dan hasilnya
   benar; hampir semua yang menentukan **ongkosnya** — 9 turn REPRODUCE + 4 turn FIX, yaitu
   sekitar setengah dari seluruh run — adalah akar-harness. Papan skor tidak merekam satu
   pun dari ongkos itu.

---

## Autopsi django-11039 — full green yang dibayar dengan satu run gugur
## (bot-01, 2026-07-20)

**Korpus:** `artifacts/r-dev/r-dev--django__django-11039--r1` (GAGAL, `wrong-logic`,
17 turn, 10 attempt), `--r2` (qualified, 21 turn, 12 attempt),
`artifacts/l-dev/l-dev--django__django-11039--r1` (qualified, 2 turn),
`artifacts/f-dev/f-dev--django__django-11039--r1` (menang attempt 1, 7 turn).
Gold: `cases/gold/django__django-11039/gold.patch`. Bug: `sqlmigrate` membungkus outputnya
dengan `BEGIN`/`COMMIT` berdasarkan `migration.atomic` saja, tanpa memeriksa
`connection.features.can_rollback_ddl`.

**Hasil (terverifikasi ulang dari artefak):** FULL GREEN. `swebench_eval.json` →
`resolved=true`, `patch_successfully_applied=true`, F2P **1/1**
(`test_sqlmigrate_for_non_transactional_databases`), P2P **88/88**, `f2p_failed=[]`,
`p2p_failed=[]`. `gold_eval.json` fase FIX: `file_match: true`, `line_overlap: true`.
LOCALIZE `pointed_lines: [55, 60]`, `line_overlap: true` — **kali ini sitasinya tepat**
(bandingkan 13230 dan 12286 di LV-13b).

**Kenapa r1 gugur — dan sebabnya bisa ditunjuk ke satu baris.** Setelah judge menolak
checkpoint in-process-nya, model membangun backend database sintetis:

> `class DatabaseWrapper(DatabaseWrapper):` dengan `features = DatabaseFeatures()` sebagai
> **class attribute**.

`BaseDatabaseWrapper.__init__` menimpanya lewat `self.features = self.features_class(self)`,
jadi `can_rollback_ddl` tetap `True` dan **gold patch tidak mengubah apa pun**:
`flip_run.json` r1 menunjukkan dunia gold masih mencetak `BEGIN; ... COMMIT;` +
`REPRO_STATUS: FAIL`. Verdict `wrong-logic`, alasan *"likely gold-unsatisfiable predicate"*.
r2 memperbaikinya dengan override di `__init__` sesudah `super().__init__()`.
**Checkpoint r1 yang dibuang memenuhi gold** (verifikasi tekstual, lihat LV-08) — jadi
kegagalan ini bukan "model tidak paham bug-nya", melainkan model dipaksa pindah ke ruang
desain yang belum diuji siapa pun, lalu tersandung di sana.

**Nol retry yang sebabnya "salah paham bug"** — konsisten dengan 13660, 13230, 12915, 12286.
Pemahaman model benar sejak awal di kedua run (`repro.md` r1 t9 menyebut baris 56
`self.output_transaction = migration.atomic` dengan tepat).

**Ke mana temuan run ini masuk (semuanya bukti penguat — NOL entri baru):**

- LV-01 — bukti penguat keenam: predikat `if BEGIN and COMMIT: FAIL else: PASS`, nol kontrol
  positif, `output_transaction = False` tanpa syarat akan lolos.
- LV-05 — bukti penguat kelima: judge menolak **2 dari 2 run** setelah exec-pair hijau
  disaksikan; r2 kategori murni `mechanics` (case ketiga di mana (b) tepat sasaran), r1
  campuran; dan **pertama kalinya penolakan judge bisa ditunjuk sebagai sebab langsung sebuah
  verdict gagal**.
- LV-06 — bukti penguat keempat: nama ketujuh (`ValueError: ready_token is required`) +
  sweep frekuensi yang menaikkan kelas one-shot dari "3 case, 8 kejadian" ke
  **5 case, 27 kejadian**; sekaligus menutup kandidat lever "Python 3.6" dari catatan penutup
  12915 butir 6 sebagai bagian dari LV-06, bukan entri sendiri.
- LV-08 — bukti penguat kelima, dan yang terkuat: checkpoint dibuang **2 dari 2 run**, dan di
  r1 selisihnya adalah **lolos vs gugur**. Pola "checkpoint lebih baik daripada penggantinya"
  kini **5 dari 5 case**.
- LV-10(b) — bukti penguat: rantai degradasi tiga langkah terekam dalam satu run
  (token `ERROR` → pesan tanpa token → cabangnya dihapus), plus frekuensi kosakata
  "tidak tahu" di **5 dari 23 case**.
- LV-14 — bukti penguat ketiga, dan ia menandai **batas** instrumentasi (a): divergensi
  fungsional nol, tetapi model membiarkan komentar lama yang kini berbohong terhadap kodenya;
  `gold_only_symbols` akan kosong dan melaporkan "setara".

**Vonis atas pertanyaan "apakah ini mekanisme baru": BUKAN.** Pertanyaan yang diajukan adalah
apakah "kualitas repro menurun antar-rerun dan gate menyeleksi yang lebih permisif" berdiri
sebagai mekanisme sendiri. Jawaban dari bukti: **tidak, dua kali.** (i) Penurunan yang
**terekam kausal** terjadi **di dalam** r1 (t15 → t16), dan akarnya adalah regex dua-nilai di
`reproduce_gates.py` baris 11 — yaitu LV-10(b), titik vonis yang sama, perbaikan yang sama.
(ii) Perbedaan r1 → r2 **bukan seleksi atas kelonggaran**: r1 gugur karena predikat
gold-unsatisfiable, sama sekali bukan karena penjaganya. Per aturan main #4, ini bukti
penguat, bukan entri. Yang **sah** dinaikkan dari observasi ini adalah rumusan yang lebih
sempit: **loop retry menggeser distribusi bentuk repro ke arah permisif, dan karena kita
rerun sampai qualified, script yang dibekukan adalah sampel dari distribusi yang sudah
bergeser.** Itu memperkuat LV-10(b) dan tidak menuntut lever baru.

---

## Komparasi kontras django-13658 (LULUS PALSU) vs django-11179 (hijau asli)
## (bot-01, 2026-07-20)

**Korpus 13658:** `artifacts/r-dev/r-dev--django__django-13658--r1` (qualified, 16 turn,
4 attempt), `artifacts/l-dev/l-dev--django__django-13658--r1` (qualified, 2 turn,
`line_overlap: false`), `artifacts/f-dev/f-dev--django__django-13658--r1`
(attempt 1 **exhausted** 40 turn di file gold dengan `attempt-1.diff` **kosong 0 byte**;
attempt 2 **win** 7 turn di file NON-gold). Gold: `cases/gold/django__django-13658/gold.patch`.

**Korpus 11179:** `r-dev--...--r1` (qualified, 6 turn, 3 attempt),
`l-dev--...--r1` (qualified, 3 turn, `file_match` + `line_overlap` true),
`f-dev--...--r1` (attempt 1 **win**, 5 turn). `resolved=true`, F2P 1/1, P2P 40/40,
`file_match: true`, `line_overlap: true`.

**Hasil di papan skor — identik. Di disk — tidak.** 13658: `resolved=true`, F2P 1/1,
P2P **181/181**, `pass_l1=true`, **`file_match: false`**, `line_overlap: null`.
11179: `resolved=true`, F2P 1/1, P2P 40/40, `file_match: true`, `line_overlap: true`.
Dua field itu adalah **satu-satunya** tempat perbedaannya terekam.

### Mekanisme lulus-palsu 13658 — diverifikasi eksekusi, dan HASILNYA MENGOREKSI hipotesis awal

Hipotesis yang dibawa ke autopsi ini: *"model lolos karena konstanta hardcoded `"django-admin"`
kebetulan persis string yang di-assert test"* — yaitu kelas **"menghafal nilai fixture"**.
Hipotesis itu diuji di dalam image case ini dan **terbantah**. Yang benar lebih buruk.

**Fakta 1 — string yang di-assert test tidak diproduksi oleh kode yang disentuh patch mana pun.**
F2P resmi berbunyi:

> `with mock.patch('sys.argv', [None] + args): execute_from_command_line(['django-admin'] + args)`
> lalu `assertIn('usage: django-admin shell', out.getvalue())` dan `assertEqual(err.getvalue(), '')`.

Baris `usage: django-admin shell` dicetak oleh parser **sub-command** (`base.py:280`), yang
sudah menerima `prog` eksplisit dari `self.prog_name` **di base yang belum dipatch sama sekali**.
Bug-nya ada di parser **top-level** (`__init__.py:347`), yang di base jatuh ke default argparse
`os.path.basename(sys.argv[0])` → `basename(None)` → `TypeError`. Jadi test ini gagal di base
**karena crash**, bukan karena string yang salah.

**Fakta 2 — eksperimen sabotase.** Patch berikut dipasang di titik gold, membaca **nol** dari argv:

> `parser = CommandParser(prog='ZZZ-NGAWUR', usage='%(prog)s subcommand [options] [args]', ...)`

Hasil `runtests.py admin_scripts.tests.ExecuteFromCommandLine.test_program_name_from_argv`:
base + test patch → **FAILED (errors=1)**; sabotase → **OK**. Yaitu: **konstanta yang ngawur,
yang jelas-jelas salah menurut judul test-nya sendiri, LOLOS F2P.**

**Kesimpulan yang menggantikan hipotesis awal.** Test `test_program_name_from_argv` — yang
docstring-nya berbunyi *"Program name is computed from the execute_from_command_line()'s argv
argument, not sys.argv"* — **tidak menguji pernyataan itu sama sekali.** Daya bedanya
seluruhnya **crash vs tidak-crash**. Setiap patch yang membuat `__init__.py:347` berhenti
melempar `TypeError` akan lolos, termasuk patch model, termasuk `prog='ZZZ-NGAWUR'`.
Konstanta `"django-admin"` di patch model **bukan** sebab kelulusan; kalau ia diganti string
lain, run ini tetap `resolved=true`. Jadi ini **bukan** kelas "menghafal nilai fixture" —
vonis lengkapnya di butir 2 catatan penutup.

**Fakta 3 — apa yang sebenarnya berbeda, terukur.** Instrumentasi `prog` atas setiap
`CommandParser` yang dibuat, tiga dunia (base / model / gold), di dalam image:

- argv pemanggil `['my_prog',...]`, `sys.argv[0]='/usr/local/bin/other_prog'` →
  parser top-level: gold `'my_prog'`, model `'/usr/local/bin/other_prog'`.
- argv pemanggil `['my_prog',...]`, `sys.argv[0]=None` →
  gold `'my_prog'`, model `'django-admin'`.
- skenario test resmi (argv pemanggil `['django-admin',...]`, `sys.argv[0]=None`) →
  gold `'django-admin'`, model `'django-admin'`. **Di sinilah keduanya bertemu**, dan hanya
  di sini.

Dan satu regresi yang tidak diminta siapa pun: karena patch model bekerja di **konstruktor**,
ia ikut mengubah pemanggil kedua tanpa `prog`, `utils.py:118`
(`get_command_line_option`), dari `os.path.basename(sys.argv[0])` menjadi `sys.argv[0]` utuh
berikut path — terukur `'my_prog'` → `'/usr/local/bin/my_prog'`, sementara gold membiarkannya
`'my_prog'`. **181 P2P hijau tidak melihatnya.** (Hanya ada dua pemanggil tanpa `prog` di
seluruh `django/`; `base.py:280` mengoper eksplisit.)

**Peringatan pembacaan, supaya klaim ini tidak melar:** satu hal yang TIDAK boleh dikatakan
adalah bahwa patch model "merusak sesuatu yang tadinya baik" dalam arti yang besar. Terhadap
base, ia perbaikan — crash-nya hilang. Yang benar dikatakan: ia **memperbaiki gejala (crash)
tanpa memperbaiki kontrak (program name dari argv pemanggil)**, dan **menggeser perilaku satu
call site yang tidak ada hubungannya**. Dua-duanya di luar jangkauan seluruh alat ukur kita.

### Kenapa 11179 hijau, dan kenapa itu juga bukan validasi

`instance.pk = None` (model) vs `setattr(instance, model._meta.pk.attname, None)` (gold)
**setara**, diverifikasi di image: `base.py:571` pada commit ini adalah
`def _set_pk_val(self, value): return setattr(self, self._meta.pk.attname, value)`.
Tetapi hijau di sini **tetap tidak membuktikan gate bekerja**, dan alasannya sudah jadi tema
berulang: ruang fix-nya sempit (satu baris, satu file, sudah ditunjuk LOCALIZE dengan
`line_overlap: true`). Repro-nya sendiri **K4** — fix yang menyetel `instance.pk = None`
lalu `return 0, {}` **tanpa menjalankan `delete_batch`** akan tetap lolos, karena repro tidak
pernah mengecek barisnya terhapus dari DB. Ini alasan **keenam** untuk tidak membaca kolom
hijau sebagai validasi (setelah 11099, 14017, 13230, 12915, 12286).

Yang membuat 11179 tetap berguna sebagai pembanding bersih: ia menunjukkan bahwa **selisih
antara dua run yang di papan skor identik dapat sepenuhnya diringkas oleh dua field yang sudah
ada di disk** — `file_match` true vs false. Bukan oleh analisis baru, bukan oleh eksekusi ulang.

### Ke mana temuan kedua run ini masuk (NOL entri baru)

- **LV-01** — bukti penguat ketujuh (13658: predikat crash-vs-tidak-crash, dan ia **sudah**
  membangun skenario `my_prog` yang membedakan lalu membuang hasilnya) dan kedelapan
  (11179: K4 menggigit walau predikatnya berbasis nilai).
- **LV-13(b)** — titik data ketiga: `evidence` 13658 menyebut `ManagementUtility.__init__`
  (~baris 123) untuk panggilan yang ada di `execute()` baris 347 — meleset ~220 baris,
  terbesar sejauh ini, dan sekali lagi **tidak merugikan** (3 dari 3).
- **LV-14** — bukti penguat keempat (13658: case pertama di mana sinyal harness sendiri
  akan menandai lulus-palsu; usul sub-item berongkos nol) dan kelima (11179: batas (a) di
  sisi **false positive**, melengkapi batas false-negative dari 11039).

---

## Catatan penutup komparasi 13658 vs 11179 (bot-01, 2026-07-20)

1. **Vonis atas kandidat "detektor lulus-palsu" (`resolved=true` ∧ `file_match=false`):
   BUKAN entri baru — ia bagian dari LV-14, dan bentuknya adalah STATE DASHBOARD.** Tiga
   alasan, berurut dari yang paling mengikat:
   (i) **Aturan main #4.** Mekanismenya — *harness sudah memegang perbandingan terhadap gold,
   sudah menuliskannya, dan tidak ada satu konsumen pun* — adalah **persis** diagnosa
   akar-harness LV-14 butir 2, kata per kata. Yang berbeda hanya field-nya (`file_match` vs
   `gold_only_symbols`) dan ongkosnya, bukan mekanismenya.
   (ii) **Bedanya dengan LV-14(a) adalah ongkos, dan itu argumen untuk MENDAHULUKAN, bukan
   untuk MEMISAHKAN.** LV-14(a) menuntut komputasi baru; ini nol. Karena itu ia dicatat
   sebagai **sub-item (a0)** di dalam LV-14: munculkan `resolved` + `file_match` berdampingan
   sebagai state dashboard, sejajar dengan ANOMALY yang sudah ada untuk kebalikannya
   (*product FAIL tapi `resolved=true`*). Nama yang diusulkan: **`OFF-GOLD`**.
   (iii) **Ia bukan detektor lulus-palsu, dan menamainya begitu akan menanam overclaim.**
   `file_match=false` berarti *"patch mendarat di file lain"* — bukan *"patch salah"*. Fix
   yang benar di file berbeda sepenuhnya mungkin, dan sebaliknya **seluruh empat lulus-palsu
   lain di korpus (12915, 12286, dan setiap divergensi isi-hunk) ber-`file_match: true`** —
   yaitu detektor ini **tidak akan menangkap satu pun dari mereka**. Recall-nya rendah secara
   struktural. Yang sah diklaim: ia **sinyal berongkos nol dengan presisi yang belum diukur**,
   dan di korpus ini 1 dari 1 kemunculannya memang lulus-palsu. n=1 untuk presisi.
2. **Vonis atas kandidat kelas "lolos karena menghafal nilai fixture": KELASNYA TIDAK ADA
   di case ini — premisnya terbantah eksperimen.** Konstanta `"django-admin"` bukan sebab
   kelulusan; `prog='ZZZ-NGAWUR'` juga lolos. Yang sebenarnya terjadi adalah **F2P resmi yang
   daya bedanya hanya crash-vs-tidak-crash**, padahal docstring-nya mengklaim menguji asal
   program name. Itu **batas metodologi** — instansi kedua dari Catatan penutup 12915 butir 1
   — dan **bukan** varian LV-01 (usulan LV-01 adalah *perketat repro*; tidak ada versi dari
   usulan itu yang bisa menjangkau test suite SWE-bench), **bukan** mekanisme baru.
   **Yang BARU dan layak dinaikkan bukan kelasnya, melainkan kelas buktinya:** di 12915 batas
   metodologi ditegakkan lewat **pembacaan** dua diff; di 13658 ia ditegakkan lewat
   **eksperimen sabotase yang bisa diulang siapa pun** — pasang konstanta ngawur, jalankan F2P,
   lihat OK. Itu teknik yang bisa dipakai ulang untuk **mengukur** daya beda F2P mana pun, dan
   dicatat di sini sebagai metode, bukan sebagai lever.
   *Contoh hipotetis yang dibawa dari autopsi 11179 (fix disempitkan ke `app_label ==
   'repro_app'` akan lolos repro karena repro cuma punya satu app) adalah hal yang BERBEDA
   dan tetap **LV-01 + K4**: di sana yang tertipu adalah repro buatan model. Di 13658 yang
   tertipu adalah **test resmi**. Jangan digabung — sumber kelonggarannya beda dan, seperti
   sudah dicatat di 12915 butir 2, **konsekuensinya beda**: yang satu masih punya lapis
   berikutnya yang bisa melihat, yang satu tidak.*
3. **Sinyal jenuh: konfirmasi keenam, dan kali ini di autopsi yang paling menjanjikan.**
   13658 dibawa ke meja sebagai *lulus palsu* — kategori yang belum pernah diautopsi langsung
   — dan tetap menghasilkan **nol mekanisme baru**: seluruh temuannya mendarat di LV-01,
   LV-13(b), dan LV-14. Pembacaan yang paling jujur tidak berubah dari catatan penutup 12286
   butir 3, hanya menguat: **nilai marjinal autopsi berikutnya sekarang jelas lebih rendah
   daripada nilai memasang LV-09 + LV-10(a) + LV-05(b), dan — baru dari batch ini —
   LV-14(a0), yang ongkosnya nol.**
4. **Satu hal yang case ini ubah soal prioritas LV-14.** Baris Prioritas LV-14 berbunyi
   *"rendah sebagai lever, sedang sebagai instrumentasi"*, dengan alasan antara lain bahwa
   biayanya *"bukan di run ini, melainkan di ketidaktahuan yang menumpuk lintas papan skor"*.
   13658 mengubah itu dari argumen menjadi **angka**: ketidaktahuan itu kini punya satu
   anggota yang teridentifikasi, dan biaya untuk berhenti tidak-tahu tentangnya adalah
   **nol** (field-nya sudah tertulis). Rekomendasi: pasang **(a0) lebih dulu dan terpisah**
   dari (a) — ia tidak menunggu spec apa pun.
5. **Akar-model vs akar-harness, jujur.** *13658:* akar-model pada patch yang memperbaiki
   gejala alih-alih kontrak, dan pada repro yang membuang skenario pembeda yang sudah ia
   bangun sendiri. **Tetapi** — sama seperti catatan adil di LV-14 untuk 12915 dan 12286 —
   **tak satu pun alat ukur menanyakannya**: repro tidak, F2P tidak, 181 P2P tidak. Akar-harness
   di sini bukan pada vonisnya (yang sah menurut definisinya) melainkan pada **kebutaan papan
   skor terhadap sinyal yang sudah ia miliki sendiri**. *11179:* nyaris tidak ada yang bisa
   dikeluhkan pada run-nya — 5 turn, 1 attempt, patch setara gold; yang tersisa hanyalah bahwa
   hijaunya, sekali lagi, tidak membuktikan apa pun tentang gate.

---

## Autopsi trio 14382 / 14238 / 13590 — spektrum kualitas repro, diukur bukan dibaca
## (bot-01, 2026-07-20, sesi ketiga)

**Hasil kelas baru: NOL.** Ketiga run masuk ke LV-01 dan LV-10 sebagai bukti penguat.
Nilai sesi ini seluruhnya ada di **pemisahan dua sumbu yang selama ini menyatu** dan di
angka frekuensi. Kandidat yang ditolak ada di catatan penutup.

### Fakta dasar ketiga run (diverifikasi dari artefak, bukan dari laporan)

- **`django-14382` — HIJAU.** `resolved=true`, F2P 1/1
  (`test_trailing_slash_in_target_app_directory_name`), P2P 188/188, `file_match` +
  `line_overlap` true di L dan F. Repro qualified = r2 (r1 gugur, lihat di bawah).
- **`django-14238` — HIJAU.** `resolved=true`, F2P 2/2, P2P 39/39, `file_match` +
  `line_overlap` true. Patch setara gold. Jebakan `_subclasses` di problem statement
  **tidak termakan** — model mendiagnosis `__subclasscheck__` dengan benar.
- **`django-13590` — MERAH.** `resolved=false`. F2P 1/1 **lulus**
  (`test_range_lookup_namedtuple`), tetapi **P2P regresi 1 dari 145**:
  `test_range_lookup_allows_F_expressions_and_expressions_for_integers`,
  `TypeError: tuple() takes at most 1 argument (2 given)` di `sql/query.py:1087`
  (`p2p_passed_count: 144` + 1 gagal). `file_match=true`, `line_overlap=true` di F —
  **lokasi tepat, logika kurang. Ini bukan lulus palsu**, dan penting bahwa ia dicatat
  begitu: papan skor bekerja benar di sini. Yang menarik justru **repro-nya**, bukan
  vonisnya. Catatan tambahan: `l-dev` menunjuk baris 1135–1145 sementara gold di ~1077,
  jadi `l-dev` `line_overlap=false` — LOCALIZE meleset, FIX tetap mendarat benar.
  Patch model (`files/fix.diff`, terbaca langsung) menambah cabang `isinstance(value, list)`
  lalu memakai `type(value)(*(generator))` untuk sisanya: ia **melindungi `list` yang tidak
  pernah terancam** dan **membiarkan `tuple` yang justru dirusak oleh `*`**. Gold membedakan
  namedtuple lewat `hasattr(type_, '_make')`.

### (1) Apa PERSISNYA yang membedakan repro yang menolak kerusakan dari yang menelannya

Pertanyaannya diajukan sebagai: *cabang `else: PASS` vs `else: UNKNOWN`? keberadaan kontrol
positif? keduanya independen?* Jawaban dari ketiga file `repro.py`, bukan dari teori:

**Yang membedakan adalah POLARITAS CABANG FALLBACK, dan HANYA itu. Kontrol positif tidak
ada hubungannya dengan sumbu ini.**

Buktinya berbentuk pasangan terkontrol yang kebetulan tersedia lengkap:

- **13590 vs 14238 — keduanya K4 (nol kontrol positif), hasilnya berlawanan.** 13590 tidak
  punya satu pun kontrol positif, dan tetap menolak 3 dari 4 kerusakan lingkungan. 14238
  juga tidak punya kontrol positif, dan menelan 4 dari 4. Satu-satunya perbedaan struktural
  yang relevan ada di cabang terakhir:
  - 13590 baris 75–78: `except Exception: traceback.print_exc(); print("REPRO_STATUS: UNKNOWN")`
  - 14238 baris 82–83: `else: print("REPRO_STATUS: PASS")`
  Karena kontrol positifnya **konstan (nol) di kedua sisi**, kontrol positif **tidak bisa**
  menjadi penjelasnya. Ini pasangan yang cukup untuk memutuskan pertanyaan (1).
- **14382 r2 — punya kontrol positif, TAPI fallback-nya juga sudah benar** (`else:
  REPRO_STATUS: ERROR`, baris 50–52). Jadi ia **tidak memisahkan** kedua faktor, dan tidak
  boleh dipakai sebagai bukti bahwa kontrol positif yang menolak kerusakan.

**Mekanisme sebenarnya, dinyatakan setepat mungkin.** Yang menentukan bukan kata `else`
melainkan **bagaimana kegagalan direpresentasikan saat sampai ke titik vonis**:

- Di **13590** pekerjaan berjalan **in-process**. Kerusakan lingkungan tiba di titik vonis
  sebagai **objek exception** — sebuah nilai yang secara tipe berbeda dari hasil normal, dan
  karenanya **tidak bisa** disamakan dengan hasil normal. Bahasanya sendiri yang memisahkan.
- Di **14238** pekerjaan berjalan di **subprocess**, dan hasilnya diperiksa dengan
  **pencocokan substring atas stdout**. Lapisan itu **menghapus perbedaan tipe**: crash,
  sukses, dan "tidak terjadi apa-apa" semuanya menjadi *string yang tidak cocok*. Setelah
  informasi itu hilang, cabang mana pun yang tersisa akan salah — dan model memilih PASS.
  **Buktinya bahwa ini soal pembuangan informasi, bukan kemalasan model:** anaknya
  **sudah menamai kegagalannya dengan benar** di baris 57–58
  (`except Exception as e: print(f"OTHER_ERROR: {type(e).__name__}: {e}")`); pemanggilnya
  hanya tidak pernah menanyakan token itu.
- Di **14382 r1** (yang gugur) lapisannya juga subprocess + substring, dan polaritas
  fallback-nya kebetulan **FAIL** — sehingga kegagalan setup terbaca sebagai "bug masih ada"
  dan repro menjadi gold-unsatisfiable.

**Jadi rumusan yang tepat, dan ini yang harus dipakai untuk membentuk lever:**
> Repro menolak kerusakan **kalau dan hanya kalau ada jalur di mana "gagal mengamati"
> mencapai titik vonis sebagai nilai yang secara struktural berbeda dari hasil normal.**
> `except Exception` in-process memberikannya gratis. Subprocess + substring
> **menghancurkannya**, kecuali pemanggil ikut mencocokkan token kegagalan yang dicetak
> anaknya.

Yang kedua itu **mekanis, murah, dan bisa dicek statis** — dan ia menjelaskan 11910, 12286,
11039, dan 14238 dengan satu kalimat yang sama.

**Apakah keduanya independen? YA, dan itu terbukti dua arah:**
- 13590 = fallback benar, kontrol positif nol → **kuat di sumbu lingkungan, buta di sumbu
  semantik** (D1 dan D2 lolos).
- 14382 r2 = kontrol positif ada dan menyala → **tidak membuatnya tajam di sumbu semantik**;
  ia tetap K5 dan tetap tidak membedakan `rstrip` dari normalisasi penuh gold.
Dua sumbu, dua lever, tidak saling menggantikan.

### (2) Vonis: "menolak kerusakan lingkungan TAPI buta terhadap kerusakan semantik" LAYAK dicatat

**LAYAK — sebagai pembedaan, bukan sebagai kelas baru.** Alasannya bukan bahwa ia menarik,
melainkan bahwa **ia mengubah bentuk lever yang benar**, dan tanpa dicatat kita akan memasang
lever yang salah dengan percaya diri:

- Uji sabotase dinamis yang sudah tertulis di **LV-10(b)** (*jalankan repro tanpa repo; kalau
  PASS, cacat*) akan **meluluskan 13590 dengan nilai sempurna**. 13590 tetap meloloskan D1
  dan D2. Kalau (b) dipasang sendirian dan hasilnya dilaporkan sebagai "kualitas repro",
  kita memproduksi **rasa aman yang salah** pada seluruh kelompok repro bertipe 13590.
- Karena itu keduanya dicatat **terpisah**, bukan digabung:
  - **LV-10(b) harus dirumuskan sebagai *"yardstick armed"*** — dan rumusannya diperketat
    dari "jangan jatuh ke PASS" menjadi **"token ketiga wajib"**, karena 14382 r1
    membuktikan `else: FAIL` merusak dengan cara yang berbeda tapi tidak lebih murah.
  - **LV-01 harus dirumuskan sebagai *"yardstick aimed"*** — kontrol positif (K4) **plus**
    assert atas nilai/struktur (K5), dan **keduanya diperlukan**: 14382 r2 punya K4 yang
    benar dan tetap K5; 11179 punya K5 yang benar dan tetap K4.
- Sudah dicatat sebagai baris tambahan di **LV-01** (bukti penguat kesembilan/kesepuluh/
  kesebelas) dan **LV-10** (dua bukti penguat baru untuk bagian b). **Nol entri baru.**

### (3) Fakta yang tidak nyaman: untuk 13590, suite resmi pun tidak membedakan D1 dari gold

**Vonis: ini instansi KETIGA "batas metodologi", dan yang paling bersih dari ketiganya.**

- **Instansi pertama** (12915/12286, LV-14): patch berbeda dari gold, tak ada alat ukur yang
  membandingkan isinya.
- **Instansi kedua** (13658, KH-06): daya beda F2P resmi ternyata cuma crash-vs-tidak-crash,
  dibuktikan dengan sabotase `prog='ZZZ-NGAWUR'` yang tetap lulus.
- **Instansi ketiga (ini):** D1 (`return [...]` — selalu paksa ke `list`, yaitu **membuang
  pelestarian tipe yang merupakan seluruh isi bug ini**) lolos **repro DAN suite resmi**.
  Bandingkan dengan D2, yang lolos repro tapi **ketahuan** suite resmi
  (`OperationalError: no such column`) — jadi di case yang sama, pada titik kode yang sama,
  L2 punya daya beda untuk satu sabotase dan nol untuk sabotase lainnya.

**Kenapa ini instansi yang paling bersih.** Di 13658 masih bisa diperdebatkan bahwa test-nya
memang tidak dimaksudkan menguji string. Di sini tidak ada ruang debat: judul issue-nya
adalah *"named tuples used as arguments to `__range` to error"*, gold-nya secara eksplisit
mendeteksi namedtuple lewat `hasattr(type_, '_make')` **supaya tipenya lestari**, dan D1
membuang pelestarian tipe itu sepenuhnya sambil tetap hijau. **F2P `test_range_lookup_namedtuple`
karenanya juga hanya menguji crash-vs-tidak-crash** — tanda tangan identik dengan KH-06,
di case yang tidak berhubungan sama sekali. Ini kemunculan kedua tanda tangan itu, dan
itulah yang membuatnya lebih dari anekdot.

**Yang TIDAK boleh disimpulkan dari ini, dan pemisahannya wajib:**
- **Bukan** "SWE-bench cacat". Yang terukur adalah: **daya beda F2P adalah variabel yang
  belum pernah kita ukur**, dan dua kali diukur, dua kali hasilnya lebih rendah dari yang
  diasumsikan. n=2. Itu bukan angka; itu alasan untuk mengukur lebih banyak.
- **Bukan** alasan untuk melonggarkan pembacaan `resolved=false` di 13590. Regresi P2P-nya
  nyata dan patch-nya memang salah. Batas metodologi di sini **tidak** menyelamatkan model.
- **Bukan** kelas baru. Ia masuk sebagai instansi ketiga di bawah payung yang sudah ada.

### Catatan penutup — kandidat yang DITOLAK dan syarat menaikkannya

Aturan katalog #5 mewajibkan ini ditulis, lengkap dengan syarat kapan boleh naik.

1. **"LV-15 — cabang fallback wajib token ketiga" (sebagai entri sendiri) — DITOLAK.**
   Alasan: ini **persis** LV-10(b), hanya dengan rumusan yang lebih tepat. Menamainya ulang
   akan memindahkan label, bukan menambah pengetahuan — pola kesalahan yang sudah dicatat
   di `koreksi-hipotesis.md` ("terlalu cepat menamai kelas baru").
   **Syarat naik:** kalau kelak (b) dipasang **dan** terbukti bahwa menuntut token ketiga
   saja tidak cukup karena ada bentuk kegagalan yang bahkan tidak sampai ke cabang mana pun
   (mis. proses dibunuh OOM/timeout), maka *deteksi kematian di luar cabang* layak jadi
   entri sendiri. Sekarang **nol bukti** untuk itu di korpus.
2. **"LV-16 — repro dilarang memakai subprocess + substring" — DITOLAK.**
   Alasan: sudah tercakup **LV-12** (preferensikan repro in-process). Menambahnya sebagai
   larangan baru akan membuat dua entri saling bertabrakan di titik yang sama, dan
   larangannya juga terlalu lebar — 14382 r2 memakai subprocess dan **benar**.
   **Syarat naik:** kalau sweep menunjukkan bahwa repro subprocess+substring punya laju
   K1-ketat yang jauh di atas repro in-process **pada denominator yang cukup**
   (usul: ≥ 10 case per kelompok). Sekarang: dari 4 anggota K1-ketat, **4-4-nya**
   subprocess+substring (11039, 11910, 12286, 14238) dan tidak satu pun repro in-process
   masuk K1-ketat — arahnya **sangat sugestif**, tetapi n=4 dan kelompoknya tidak seimbang,
   jadi belum boleh diangkat. **Ini kandidat yang paling dekat naik dari sesi ini, dan
   pengukurannya murah** — cukup klasifikasi in-process vs subprocess atas 27 file yang
   sudah ada.
3. **"Kelas baru: gold-unsatisfiable karena setup tidak lengkap" — DITOLAK sebagai entri.**
   Alasan: 14382 r1 dan 11039 r1 memang dua kejadian, tetapi **sebabnya berbeda** (setup
   tidak lengkap vs predikat yang salah konstruksi) dan **gejalanya sama persis dengan
   seluruh 41 run `wrong-logic`** di korpus — yaitu label catch-all yang sudah dikeluhkan
   di LV-10 Akibat #3. Menamai satu sub-sebab sebagai kelas sementara 41 run lain belum
   dipilah adalah cara termahal untuk belajar. Dicatat sebagai bukti penguat di LV-10(b)
   dengan polaritas fallback sebagai mekanisme pemersatunya.
   **Syarat naik:** pilah lebih dulu seluruh **41 run `wrong-logic` / 10 case** berdasarkan
   `flip_run.json` (gold masih FAIL vs gold ERROR vs gold tidak mencetak status). Kalau
   sub-sebab "setup tidak lengkap" ternyata ≥ 5 case, ia layak jadi entri — dan levernya
   kemungkinan besar adalah verdict terpisah, bukan lever repro.
4. **"Daya beda F2P resmi rendah" sebagai entri lever — DITOLAK.**
   Alasan: ini **batas metodologi**, bukan akar-harness kita; tidak ada lever di dalam
   kendali kita yang menyerangnya, dan aturan #6 melarang lever yang menyerang akar yang
   salah. **Syarat naik:** kalau kita memutuskan untuk **mengukur** daya beda F2P secara
   sistematis (sabotase gold di titik gold untuk tiap case), maka *harness pengukurnya*
   layak jadi entri — sebagai alat, bukan sebagai keluhan. Sekarang n=2 (13658, 13590).

---

## Tabel frekuensi kelas kegagalan (per 2026-07-20)

**Section ini BOLEH diperbarui** — beda dari entri lever yang append-only. Setiap pembaruan
wajib bertanggal dan menyebut denominatornya. Alasan keberadaannya: setelah lima autopsi
berturut-turut tanpa mekanisme baru, yang kurang bukan lagi katalog kelas melainkan
**urutan prioritas berbasis frekuensi**.

### Metode dan denominator (baca ini sebelum memakai angkanya)

- **Populasi run:** seluruh `artifacts/r-dev/*` = **120 run**, di antaranya **65 qualified**
  (`verdict.json` → `pass_l1: true`), tersebar di **23 case**. Plus seluruh
  `artifacts/f-dev/*` = **12 run**, 10 case.
- **Peringatan bias yang wajib dibaca bersama angka per-run:** `django-11422` sendirian
  menyumbang **44 dari 120 run** (13 qualified) karena kampanye rerun. Angka **per-run**
  karenanya condong ke satu case. Untuk K1–K5 dipakai **satu repro qualified per case**
  (run qualified terakhir tiap case) = **sampel 23 file**, sehingga tiap case punya bobot 1.
- **K1, K2, K4, K5 dinilai MANUAL**, dengan membaca 23 file itu satu per satu (1.630 baris).
  Alasannya: detektor AST yang ditulis untuk tugas ini **over-count** — ia menandai 18 run
  sebagai K1, padahal sebagian besar adalah rantai `elif` yang sisi PASS-nya justru menuntut
  bukti positif (mis. 15320: `startswith('(SELECT') and endswith(')')`). Angka otomatis itu
  **tidak dipakai** dan tidak boleh dikutip.
- **K3 dan kelas-kelas di tabel B dinilai OTOMATIS** (grep/regex atas `events.jsonl` dan
  `repro.py`) dan bisa direproduksi persis.

### Tabel A — kualitas 23 repro qualified (satu per case, penilaian manual)

- **K1 — pola vonis `if <gejala>: FAIL else: PASS`** (PASS adalah cabang "gejala tidak
  teramati"): **10 dari 23 case**. Yaitu 11039, 11099, 11910, 12286, 12747, 12915, 13158,
  13401, 13658, 14017.
- **K1-ketat — kegagalan katastrofik benar-benar mendarat di PASS** (K1 **dan** tidak ada
  penjaga exception/exit yang mengalihkannya): **3 dari 23 case** — **11039, 11910, 12286**.
  Pemisahan ini penting dan sebelumnya tidak pernah dibuat: 7 dari 10 K1 punya `except` yang
  membelokkan crash ke FAIL atau ke exit non-nol, jadi mereka longgar tetapi **tidak
  berbahaya dengan cara yang sama**. Ketiga case K1-ketat itu persis ketiga case yang sudah
  ditulis panjang di LV-01/LV-10 — jadi kelas terburuknya **memang sudah terkatalog lengkap**,
  dan frekuensinya **13%**, bukan mayoritas.
- **K2 — ada cabang yang tidak mencetak `REPRO_STATUS` sama sekali:** **8 dari 23 case**
  (10914, 11099, 11422, 11910, 12747, 12915, 13230, 13768). **Temuan yang membalik tafsir
  kriteria ini:** **3 dari 8 adalah perilaku yang BENAR** — 11422 r44 dan 13768 r4 menahan
  status justru karena **kontrol positifnya gagal**, dan 10914 r1 menahannya karena
  environment terbukti tidak bisa mereproduksi bug. K2 karenanya **bukan metrik cacat**;
  ia mengukur "model punya sesuatu untuk dikatakan yang tidak bisa diucapkan kontrak" —
  dan itu argumen untuk LV-10(b), bukan tuduhan terhadap repro-nya.
- **K3 — mengimpor `pipe_runtime`:** **4 dari 23 case** (11422, 11910, 12286, 13660);
  per-run **12 dari 65 repro qualified**. Kelas ini **tidak menyebar** — ia terkonsentrasi di
  case-case yang judge-nya mengutip `rule:app-runtime`.
- **K4 — tidak punya kontrol positif yang ikut menentukan kelulusan:** **19 dari 23 case.**
  Ini **kriteria dengan prevalensi tertinggi di seluruh tabel**, dan yang paling kurang
  terwakili di katalog: sampai sekarang ia hanya muncul sebagai anak kalimat di LV-01
  (13230, 12915, 12286). Empat yang **punya** kontrol: 10914 (precondition environment
  `tempfile` 0o600 yang menggugurkan vonis kalau tak terpenuhi), 11422 r44 (ubah `settings.py`
  dulu dan wajib melihat reloader menyala), 13768 r4 (emit log kontrol dan wajib menangkapnya),
  14017 (uji `Exists() & Q()` yang memang bekerja sebelum menguji arah yang rusak).
  Keempatnya membuktikan bentuknya **murah dan sudah ada di korpus** — jadi ini kandidat
  paling konkret untuk memberi isi pada usulan LV-01 yang selama ini buntu di *"perketat repro
  itu mudah dikatakan, sulit dimekaniskan tanpa membocorkan gold"*: **kontrol positif tidak
  butuh gold sama sekali.**
- **K5 — vonisnya cuma substring / "tidak melempar exception", bukan nilai atau struktur:**
  **12 dari 23 case** (11039, 11422, 11797, 11910, 12286, 12308, 12915, 13658, 13660, 13768,
  14017, 15320). Sebelas sisanya memakai perbandingan nilai/struktur
  (mis. 13220 `err1 == err2`, 13401 `set_len == 1`, 15400 `result == 15`,
  13230 `comments == "http://comments/1/"`). Jadi **hampir tepat separuh** korpus qualified
  bertumpu pada bukti tekstual/negatif.

**Irisan yang paling layak dibaca:** **K4 ∧ K5 = 10 dari 23 case** — separuh korpus qualified
memutuskan nasib sebuah fix dari sebuah substring, tanpa satu pun cek bahwa alat ukurnya
menyala. Itu, bukan K1, adalah profil kelemahan yardstick yang sebenarnya.

### Tabel B — frekuensi kelas kegagalan (otomatis, seluruh 120 run `r-dev`)

Dihitung dari `detail.why` di `events.jsonl`. Satu event = satu kejadian.

- **Penolakan judge menahan DONE** (LV-05): **20 kejadian, 20 run, 11 dari 24 case.**
  Ini kelas dengan **sebaran case terluas** di korpus — tersentuh oleh hampir separuh case,
  bukan hanya oleh yang sudah diautopsi. **Catatan kejujuran yang wajib menyertainya:**
  dari 20 run yang ditahan judge, **12 tetap berakhir qualified (60%)**, sementara laju
  qualified korpus keseluruhan **54% (65/120)**. Jadi di tingkat agregat, penolakan judge
  **tidak terlihat menurunkan laju kelulusan**. Ongkosnya terbukti nyata dalam **turn**
  (13230: 7; 12915: 16; 12286: 9; 11039: 7 dan 8) dan **sekali** dalam verdict (11039 r1),
  tetapi siapa pun yang memakai tabel ini untuk membenarkan LV-05 harus memakai argumen
  ongkos-turn dan risiko-ekor, **bukan** klaim "judge menggugurkan run".
- **`App` gagal pada perintah one-shot** (LV-06): **27 kejadian, 15 run, 5 case**
  (11039, 11422, 12286, 12915, 13660). Naik tajam dari "3 case, 8 kejadian" yang tercatat
  di LV-06.
- **`__init__() got an unexpected keyword argument`** (LV-06, atribusi campuran `App` vs
  `subprocess` Python 3.6): **33 kejadian, 21 run, 8 case**; **30 dari 33 hanya dua nama**,
  `text` (16×) dan `capture_output` (14×). Ini **kelas bernama terbesar di korpus**.
- **Repro mencetak PASS di dunia base sehingga gate menolak DONE:** **83 kejadian, 14 run,
  8 case.** Angka terbesar di tabel ini, dan ia **bukan cacat** — ini gate bekerja persis
  sebagaimana mestinya, menolak repro yang belum mereproduksi. Dicatat justru sebagai
  pembanding: mekanisme yang mengikat memang menghasilkan volume penolakan seperti ini, dan
  itulah bentuk yang diharapkan dari LV-10(a) kalau dipasang.
- **`REPRO_STATUS: ERROR` muncul di aliran retry** (LV-10b): **8 kejadian, 3 run, 3 case.**
  Angka ini **jauh lebih kecil daripada prevalensi sebenarnya** dan tidak boleh dipakai
  sendirian: ia hanya menghitung kejadian di mana cabang ERROR **kebetulan menyala saat
  dinilai**. Prevalensi yang benar untuk (b) ada di Tabel A/K2 dan di bukti penguat LV-10:
  **5 dari 23 case** menuliskan kosakata "tidak tahu" dalam bentuk apa pun.

### Tabel C — LV-09 lintas seluruh `f-dev` (12 run)

`grep -c "No module named 'pipe_runtime'"` atas tiap `console.log`:

- **Repro beku mengimpor `pipe_runtime` — 5 run, 3 case:** 11910 r1 (**588** kejadian, console
  17.927 baris, `pass_l1=false`), 13660 r1 (38), 13660 r3 (6), 12286 r1 (7), 13660 r2 (3).
- **Repro beku bersih — 7 run, 7 case:** 10914, 11039, 11099, 12915, 13230, 13658, 14017 —
  **nol kejadian di ketujuhnya.**
- **Korelasi dengan hasil L2:** kelompok terpapar **1 dari 5 `resolved=true`**; kelompok bersih
  **6 dari 7**. Arahnya searah dengan bukti kode (`run_fix_gemma.py:231–232`) dan dengan lima
  titik korelasi yang sudah ditulis di LV-09.
- **Confounder yang wajib disebut, kalau tidak angka ini menyesatkan:** ketiga run 13660 gagal
  L2 karena `exec(cmd, {})` (LV-01/LV-04), **bukan** karena modul yang hilang — jadi 3 dari 5
  anggota kelompok terpapar punya sebab kegagalan yang berdiri sendiri. Dan di sisi bersih,
  14017 juga `resolved=false`. Rasio 1/5 vs 6/7 karenanya **tidak boleh dibaca sebagai efek
  kausal LV-09**; yang sah diklaim tetap seperti sebelumnya: LV-09 hanya bisa menggigit repro
  yang punya dependency runtime, dan besaran gigitannya terukur dalam turn (11910: 80 turn
  tanpa hasil; 12286: 4 dari 7 turn), bukan dalam laju resolved.

### Konsekuensi untuk urutan pemasangan

Frekuensi **tidak membalik** urutan yang sudah disarankan (LV-10a → LV-09 → LV-05b → LV-11),
tetapi ia menggeser dua hal:

1. **LV-06 naik.** Dengan 27 + 30 kejadian di 5–8 case, ia kini kelas kegagalan REPRODUCE
   terbesar yang terukur, dan perbaikannya (`App.run_once()` + `app.output()`) tidak
   menyentuh penalaran model sama sekali. Sebelumnya ia dinilai "tinggi tapi akan jarang
   terpicu kalau LV-05 dipasang duluan" — angka ini menunjukkan basisnya lebih lebar
   daripada yang bisa dihapus LV-05.
2. **Kontrol positif (K4, 19/23) layak jadi isi konkret pertama untuk LV-01.** Selama ini
   LV-01 macet karena "perketat repro" tidak punya bentuk mekanis yang tidak membocorkan
   gold. Kontrol positif **tidak membocorkan apa pun** — ia hanya menuntut script membuktikan
   bahwa alat ukurnya menyala — dan empat case di korpus sudah menuliskannya sendiri tanpa
   diminta. Ini belum dinaikkan jadi usulan resmi di LV-01 (butuh spec, dan aturan main #6
   melarang mengubah kontrak berdasarkan pengamatan yang belum diuji); dicatat di sini
   sebagai arah yang paling didukung data.

### Pembaruan bertanggal 2026-07-20 (bot-01, sesi kedua) — setelah 13658 dan 11179

**Apa yang berubah pada denominator.** Sampel Tabel A naik dari **23 → 24 case**: `django-11179`
adalah case dengan repro qualified yang belum pernah masuk hitungan. `django-13658` **sudah**
terhitung di sampel 23 (ia ada di daftar K1 dan K5), jadi ia **tidak** menambah denominator —
yang bertambah dari 13658 hanyalah bukti kualitatif di LV-01/LV-13/LV-14, bukan angka.
Sampel `f-dev` naik dari **12 → 13 run** (11179 masuk).

**Klasifikasi 11179** (dibaca manual dari `r-dev--django__django-11179--r1/files/repro.py`,
metode sama dengan sampel 23):

- **K1 — TIDAK.** Sisi PASS menuntut pengamatan positif (`if obj.pk is None: PASS`), bukan
  ketiadaan gejala. **K1-ketat — TIDAK** (`except` membelokkan crash ke `REPRO_STATUS: FAIL`).
- **K2 — TIDAK**, dengan catatan yang wajib disebut supaya tidak menyesatkan: seluruh **cabang
  vonis** mencetak status, tetapi setup di level modul (`settings.configure`,
  `schema_editor.create_model`) berada **di luar** `try`, sehingga crash di sana tidak
  menghasilkan baris `REPRO_STATUS` sama sekali. Dihitung TIDAK karena K2 mengukur *cabang*,
  konsisten dengan penilaian 23 file sebelumnya.
- **K3 — TIDAK** (nol `pipe_runtime`; in-process murni).
- **K4 — YA.** Nol kontrol positif; contoh konkretnya ditulis sebagai bukti penguat kedelapan
  di LV-01 (`instance.pk = None` + `return 0, {}` tanpa `delete_batch` akan lolos).
- **K5 — TIDAK.** Vonisnya perbandingan nilai (`obj.pk is None`), bukan substring dan bukan
  "tidak melempar exception".

**Hitungan K1–K5 yang diperbarui (denominator 24 case, satu repro qualified per case):**

- **K1:** **10 dari 24** (turun proporsinya dari 10/23; daftar case tidak berubah).
- **K1-ketat:** **3 dari 24** — 11039, 11910, 12286. Daftar tidak berubah; **13%**.
- **K2:** **8 dari 24**. Daftar tidak berubah.
- **K3:** **4 dari 24**. Daftar tidak berubah.
- **K4:** **20 dari 24** — naik satu (11179). Tetap **kriteria dengan prevalensi tertinggi**,
  kini **83%**. Empat yang punya kontrol tetap 10914, 11422 r44, 13768 r4, 14017.
- **K5:** **12 dari 24**. Daftar tidak berubah.
- **Irisan K4 ∧ K5:** **10 dari 24**. Tidak berubah (11179 K4 tapi bukan K5).

**Pembacaan yang berubah — kecil tapi searah.** 11179 adalah contoh pertama di sampel ini yang
**bagus di K1, K3, dan K5 sekaligus namun tetap K4**. Itu memisahkan dua hal yang sebelumnya
cenderung bergerak bersama: *kualitas predikat* (apa yang diperiksa) dan *bukti bahwa alat
ukurnya menyala* (K4). Konsekuensinya untuk urutan pemasangan: butir 2 di section
"Konsekuensi untuk urutan pemasangan" (di atas) **menguat** — kontrol positif tidak bisa
didapat gratis dengan memperbaiki predikat, karena repro dengan predikat terbaik di sampel
pun tidak punya.

**Pembaruan Tabel C (LV-09) yang menyertainya.** `grep -c "pipe_runtime"` atas `console.log`:
`f-dev--django__django-11179--r1` → **0**, dan `f-dev--django__django-13658--r1` → **0**
(13658 sudah terdaftar di kelompok bersih; 11179 baru). Kelompok **repro beku bersih** karenanya
menjadi **8 run, 8 case** (10914, 11039, 11099, **11179**, 12915, 13230, 13658, 14017), dengan
**7 dari 8 `resolved=true`**. Kelompok terpapar tidak berubah (5 run, 3 case, 1 dari 5).
**Confounder yang sudah ditulis di Tabel C tetap berlaku dan tidak boleh dilupakan** — rasio
ini tidak boleh dibaca kausal.

### Tabel D — `resolved=true` dengan `file_match=false` (metrik baru, 2026-07-20)

**Metode dan denominator, supaya bisa direproduksi persis.** Disweep seluruh
`artifacts/f-dev/*/` yang punya **`swebench_eval.json` DAN `gold_eval.json`**; dibaca
`resolved` dari yang pertama dan `file_match` / `line_overlap` dari yang kedua.

- **Denominator: 13 run `f-dev`, di antaranya 12 punya kedua file.** Yang tidak punya:
  `f-dev--django__django-11910--r1` (run itu `pass_l1=false`, tidak pernah sampai eval).
- **`resolved=true`: 8 dari 12.** (10914, 11039, 11099, 11179, 12286, 12915, 13230, 13658.)
- **`resolved=true` DAN `file_match=false`: 1 dari 12 run** — **`f-dev--django__django-13658--r1`**,
  satu-satunya. Dinyatakan atas denominator yang lebih tajam: **1 dari 8 run `resolved=true`**.
- **`resolved=true` DAN `line_overlap=false`: 0 dari 12.** (Di 13658 `line_overlap` adalah
  `null`, bukan `false` — konsekuensi wajar dari `file_match=false`: tidak ada file yang sama
  untuk dibandingkan barisnya. **Detektor apa pun yang dibangun di atas metrik ini wajib
  memperlakukan `null` sebagai kasus tersendiri, bukan sebagai `false` dan bukan sebagai
  "tidak ada masalah"** — kalau `null` dibulatkan ke salah satunya, satu-satunya hit di korpus
  ini hilang.)
- **Empat run `resolved=false`** semuanya `file_match=true` + `line_overlap=true`
  (13660 r1/r2/r3, 14017) — yaitu **mendarat tepat di situs gold dan tetap gagal**. Ini
  pembanding penting: kedua field ini tidak berkorelasi dengan hasil L2 ke arah mana pun di
  korpus ini. **Jangan** dibaca sebagai prediktor.

**Peringatan yang wajib menyertai angka ini, dan ia lebih besar daripada angkanya.** Metrik ini
punya **recall struktural yang rendah**: seluruh lulus-palsu lain yang sudah tercatat di
katalog (12915 dan 12286, dua-duanya divergensi isi hunk di file yang benar) ber-`file_match:
true` dan **tidak akan tersentuh sama sekali**. Jadi "1 dari 12" adalah hitungan **kemunculan
sinyal**, **bukan** perkiraan frekuensi lulus-palsu di korpus — yang terakhir itu masih
termasuk hal yang sengaja dibiarkan kosong di bawah. Presisinya di korpus ini 1 dari 1, yaitu
**n=1**. Nilai metrik ini seluruhnya terletak pada **ongkosnya yang nol**, bukan pada
cakupannya.

**Yang TIDAK bisa diukur andal, dan sengaja dibiarkan kosong:** apakah repro longgar
**menyebabkan** patch yang tidak setara gold. Untuk menjawabnya perlu `gold_only_symbols`
(LV-14a) terpasang lebih dulu di seluruh korpus; tanpa itu, satu-satunya jalan adalah membaca
setiap pasang diff dengan tangan, dan sampel yang ada (12915, 12286, 11039) terlalu kecil dan
terlalu dipilih untuk menghasilkan angka.

### Pembaruan bertanggal 2026-07-20 (bot-01, sesi ketiga) — setelah 14382, 14238, 13590

**Denominator baru, diukur ulang dari nol** (skrip sweep atas seluruh `artifacts/`, bisa
diulang):

- **`artifacts/r-dev` = 126 run** (naik dari 120), **69 qualified** (naik dari 65),
  **30 case** seluruhnya, di antaranya **27 case punya ≥1 repro qualified** (naik dari 24).
  Tiga case yang zero-qualified: 11905, 12453, 14667.
- **Kejujuran soal selisih:** ketiga case sesi ini menyumbang **4 run** (14382 r1+r2,
  14238 r1, 13590 r1) dan **3 qualified**. Run-level naik **6** dan qualified naik **4**,
  jadi **2 run / 1 qualified berasal dari luar sesi ini dan TIDAK saya audit.** Kenaikan
  case-level (24 → 27) seluruhnya milik sesi ini dan terverifikasi satu per satu.
- **Sampel Tabel A = 27 case** (satu repro qualified per case, run qualified terakhir).
  Ketiga case baru **menambah denominator**, karena tak satu pun pernah masuk hitungan.
- **`artifacts/f-dev` = 16 run** (naik dari 13), **15 punya `swebench_eval.json` DAN
  `gold_eval.json`**. Yang tetap tidak punya: `f-dev--django__django-11910--r1`.
- **Peringatan bias yang lama tetap berlaku dan justru menguat:** `django-11422` menyumbang
  **44 dari 126 run**. Angka per-run masih condong ke satu case; K1–K5 tetap per-case.

**Klasifikasi ketiga repro baru** (dibaca manual, metode sama dengan 24 file sebelumnya):

- **`14382` r2** — **K1 TIDAK** (sisi PASS menuntut pengamatan positif `elif success:`,
  bukan ketiadaan gejala). **K1-ketat TIDAK.** **K2 TIDAK.** **K3 TIDAK.**
  **K4 TIDAK — punya kontrol positif, dan load-bearing**: baris 26–34 menjalankan
  `startapp control_app control_dir` lebih dulu dan `return` dengan `REPRO_STATUS: ERROR`
  kalau gagal, sehingga cabang vonis tidak pernah tercapai. Ini **anggota kelima** kelompok
  "punya kontrol", dan **satu-satunya yang kontrolnya terbukti menyala di dalam loop**
  (`events.jsonl` r2 mencatat satu attempt berakhir `REPRO_STATUS: ERROR`).
  **K5 YA** — vonisnya substring `"'' is not a valid app directory"` atas stderr + exit code;
  tidak pernah memeriksa bahwa `bug_app/` mendarat di dalam `bug_dir/`.
- **`14238` r1** — **K1 YA** (`else: print("REPRO_STATUS: PASS")`, baris 82–83).
  **K1-ketat YA** — dan ini **anggota keempat** kelas terburuk, **yang pertama dibuktikan
  dengan eksekusi**: Django dibuat tak bisa di-import → PASS (4 dari 4 sabotase → PASS).
  **K2 TIDAK.** **K3 TIDAK.** **K4 YA** (nol kontrol). **K5 YA** (substring atas stdout anak).
- **`13590` r1** — **K1 YA** (sisi PASS = "`TypeError` tidak teramati"). **K1-ketat TIDAK**
  — `except Exception` di baris 75–78 membelokkan kegagalan katastrofik ke
  `REPRO_STATUS: UNKNOWN`, persis pola "7 dari 10" yang sudah dicatat di KH-05.
  **K2 YA**, dan **aturan yang saya pakai wajib disebut supaya bisa diaudit:** UNKNOWN
  **bukan** token yang bisa dilihat `_STATUS_RE`, jadi cabang itu efektif "tidak mencetak
  status" bagi harness. Preseden untuk pembacaan ini adalah **12915 r2**, yang **seluruh**
  cabangnya mencetak `REPRO_STATUS` (baris 74/76/78, yang terakhir `ERROR`) dan **tetap
  terdaftar di K2** pada sampel 23. Konsisten dengan preseden itu, 13590 dihitung YA.
  **Catatan penting yang harus menyertainya:** seperti 3 dari 8 anggota K2 sebelumnya, ini
  adalah **perilaku yang BENAR** — subset "K2 karena repro berlaku jujur" naik dari
  **3 dari 8** menjadi **4 dari 9**. **K3 TIDAK.** **K4 YA** (nol kontrol).
  **K5 YA** — vonisnya "tidak ada `TypeError` yang lolos", dan baris 60 bahkan **membuang
  hasil `.exists()`**.

**Hitungan K1–K5 yang diperbarui (denominator 27 case):**

- **K1: 12 dari 27** (44%). Naik dua: +14238, +13590.
- **K1-ketat: 4 dari 27** (15%). Naik satu: **+14238**. Daftar kini
  **11039, 11910, 12286, 14238**. Ini **penambahan pertama ke kelas ini sejak dibuat**, dan
  yang pertama yang keanggotaannya **dibuktikan dengan sabotase, bukan dengan pembacaan**.
  Proporsinya tetap minoritas (15% vs 13% sebelumnya) — **KH-05 tidak terbantah**, hanya
  bertambah satu titik.
- **K2: 9 dari 27**. Naik satu (+13590), dengan aturan penghitungan di atas.
- **K3: 4 dari 27** (11422, 11910, 12286, 13660). **Daftar dan angka absolutnya tidak
  berubah** — diverifikasi ulang dengan grep atas 69 repro qualified. Kelas ini tetap
  **tidak menyebar**.
- **K4: 22 dari 27** (81%). Naik dua (+14238, +13590). **Tetap kriteria dengan prevalensi
  tertinggi.** Yang **punya** kontrol kini **5**: 10914, 11422 r44, 13768 r4, 14017,
  **14382 r2**.
- **K5: 15 dari 27** (56%). Naik tiga — **ketiga case baru K5 semuanya**.
- **Irisan K4 ∧ K5: 12 dari 27** (44%). Naik dua (14238, 13590; 14382 K5 tapi bukan K4).

**Pembacaan yang berubah, dan ini yang paling layak dibawa keluar dari sesi ini.** Sampel
sebelumnya memisahkan *kualitas predikat* (K1/K5) dari *bukti alat ukur menyala* (K4) lewat
11179. Sesi ini memisahkan sumbu **ketiga** yang selama ini tersembunyi di dalam K1:
**ketahanan terhadap kerusakan lingkungan**. 13590 dan 14238 **sama-sama K1, sama-sama K4,
sama-sama K5** — dan hasil sabotasenya berlawanan total (3 dari 4 ditolak vs 4 dari 4
ditelan). Yang membedakan hanya **polaritas cabang fallback**. Artinya: **K1 sebagaimana
didefinisikan tidak memprediksi ketahanan**, dan siapa pun yang memakai K1 sebagai proksi
kualitas akan salah pada pasangan ini. Rinciannya di autopsi trio 14382/14238/13590 di atas.

**Tabel B — baris yang bisa saya hitung ulang dengan metode yang SAMA** (regex atas
`detail.why` di seluruh 126 `events.jsonl`):

- **Repro mencetak PASS di dunia base sehingga gate menolak DONE: 89 kejadian, 15 run,
  9 case** (naik dari 83/14/8). **Seluruh tambahannya dari `14238` r1** — 6 kejadian, yaitu
  6 dari 7 attempt gagalnya, semuanya kelas identik. Tetap **bukan cacat**: ini gate bekerja.
- **`unexpected keyword argument`: 33 kejadian, 21 run, 8 case.** **Tidak berubah** — nol
  kejadian di keempat run baru. Tetap kelas bernama terbesar di korpus.
- **`REPRO_STATUS: ERROR` di aliran retry: 9 kejadian, 4 run, 4 case** (naik dari 8/3/3).
  Tambahannya dari **`14382` r2**, dan itu **kontrol positif yang menyala**, bukan cacat —
  jadi baris ini kini mencampur dua hal yang berlawanan maknanya dan **tidak boleh dibaca
  sebagai laju kegagalan**.
- **`REPRO_STATUS: UNKNOWN` di aliran retry: 1 kejadian, 1 run, 1 case** (`13590` r1).
  **Baris baru.** Ini bentuk kosakata "tidak tahu" yang **kedelapan**, dan sekali lagi
  **tak terlihat `_STATUS_RE`**. Model menciptakan token ketiga di **6 dari 27 case**.
- **Dua baris yang SENGAJA tidak saya perbarui, dan alasannya:** "Penolakan judge menahan
  DONE" dan "`App` gagal pada perintah one-shot". Regex saya tidak mereproduksi angka basis
  yang tertulis (saya dapat 176/44/18 dan 2/2/2 vs 20/20/11 dan 27/15/5) — jadi matcher-nya
  **berbeda**, dan menimpa angka lama dengan angka saya akan merusak deret waktu. Yang bisa
  saya nyatakan adalah **delta dari keempat run baru saja**: judge menahan DONE **+3
  kejadian, +2 run, +1 case** (14382 r1 `done-deferred`, 14382 r2 `done-rejected`; nol di
  14238 dan 13590); `ready_token is required` **+1 kejadian, +1 run, +1 case** (14382 r1).
  Siapa pun yang memperbarui dua baris ini nanti wajib menemukan matcher aslinya dulu.

**Tabel C (LV-09) yang diperbarui** — `grep -c "No module named 'pipe_runtime'"` atas tiap
`console.log` di seluruh **16 run `f-dev`**:

- **Kelompok terpapar: TIDAK BERUBAH** — 5 run, 3 case (11910 r1 = 588, 13660 r1 = 38,
  13660 r3 = 6, 12286 r1 = 7, 13660 r2 = 3), **1 dari 5 `resolved=true`**.
- **Kelompok bersih: 11 run, 11 case** (naik dari 8/8) — 10914, 11039, 11099, 11179,
  **13590**, 12915, 13230, 13658, 14017, **14238**, **14382** — nol kejadian di semuanya.
  **9 dari 11 `resolved=true`** (yang `false`: 14017 dan 13590).
- **Confounder yang wajib ikut dibaca, dan ia BERTAMBAH satu:** rasio 1/5 vs 9/11 tetap
  **tidak boleh dibaca kausal**. Selain 3-dari-5 kelompok terpapar yang adalah 13660 dengan
  sebab kegagalan sendiri (`exec(cmd, {})`), kini kelompok bersih juga punya **dua** anggota
  `resolved=false` dengan sebab yang sama sekali tidak berhubungan dengan `pipe_runtime`
  (14017: fix sempit khusus `Exists`; 13590: `type(value)(*gen)` merusak `tuple`). Klaim
  yang sah tetap sama seperti di KH-09: LV-09 hanya menggigit repro yang punya dependency
  runtime, dan besarannya terukur dalam **turn**, bukan dalam laju resolved.

**Tabel D (OFF-GOLD) yang diperbarui** — metode identik: sweep seluruh `artifacts/f-dev/*/`
yang punya `swebench_eval.json` **DAN** `gold_eval.json`.

- **Denominator: 16 run `f-dev`, 15 punya kedua file.** Yang tidak punya tetap
  `f-dev--django__django-11910--r1` (`pass_l1=false`, tidak pernah sampai eval).
- **`resolved=true`: 10 dari 15** (naik dari 8 dari 12) — 10914, 11039, 11099, 11179, 12286,
  12915, 13230, 13658, **14238**, **14382**.
- **`resolved=true` DAN `file_match=false`: 1 dari 15** — tetap **`13658` r1**, satu-satunya.
  Atas denominator yang lebih tajam: **1 dari 10 run `resolved=true`** (sebelumnya 1 dari 8).
  **Ketiga run baru tidak menambah hit** — 14382 dan 14238 dua-duanya `file_match=true`.
  Presisi tetap 1 dari 1 (**n=1**), recall struktural tetap rendah, dan **peringatan lama
  tetap berlaku sepenuhnya**: metrik ini menghitung **kemunculan sinyal**, bukan frekuensi
  lulus-palsu.
- **`resolved=true` DAN `line_overlap=false`: 0 dari 15.** Tidak berubah. Peringatan `null`
  vs `false` di 13658 tetap berlaku dan tetap wajib dipatuhi detektor mana pun.
- **`resolved=false`: 5 run, 3 case** (naik dari 4 run, 2 case) — 13660 r1/r2/r3, 14017,
  **13590** — dan **kelima-limanya `file_match=true` + `line_overlap=true`**, yaitu
  **mendarat tepat di situs gold dan tetap gagal**. **13590 memperkuat baris ini dengan
  cara yang paling tajam sejauh ini:** `l-dev` menunjuk **salah** (baris 1135–1145, gold di
  ~1077, `line_overlap=false`) dan FIX tetap mendarat **tepat** di situs gold — lalu gagal
  karena logikanya, bukan karena lokasinya. **Kesimpulan lama diperkuat, bukan digeser:
  `file_match`/`line_overlap` tidak berkorelasi dengan hasil L2 ke arah mana pun. JANGAN
  dibaca sebagai prediktor**, dan sekarang juga: jangan baca `l-dev` `line_overlap` sebagai
  prediktor keberhasilan FIX.

**Yang TIDAK bisa diukur dan tetap sengaja dibiarkan kosong** — sama seperti sebelumnya
(apakah repro longgar *menyebabkan* patch tidak setara gold), **plus satu yang baru dan
lebih penting:** **daya beda F2P resmi**. 13590 menambah instansi kedua di mana sabotase
yang jelas merusak tetap lolos test resmi (D1; yang pertama 13658/KH-06). **n=2, dan itu
bukan angka.** Mengukurnya butuh harness sabotase-per-case yang belum ada; sampai itu ada,
jangan mengutip "batas metodologi" sebagai frekuensi.

---

## Catatan penutup autopsi batch bot-02 (2026-07-21) — estafet 22-case, bagian 7 django

**Korpus:** 7 case dijalankan RLFV penuh lewat `scripts/run_rlfv_batch.py`
(`django__django-13710, 13028, 14580, 14672, 14752, 14915, 15347`), state
`artifacts/batch-bot02.json`. Model `google/gemma-4-31B-it`. Autopsi tiap case oleh satu
subagent read-only; integrasi (tulisan ini) serial oleh bot-02. **Sabotase §3d TIDAK
dieksekusi** — lihat catatan di akhir section; rekomendasi per-case dicatat tapi tidak
dijalankan (mode frekuensi, katalog jenuh). Metode klasifikasi K1–K5 = manual, satu repro
qualified per case, konsisten dengan 27 file sebelumnya.

### Papan skor yang membedakan (bukan angka agregat)

- **Hijau ASLI (patch SETARA gold secara semantik) — 3:** 15347, 14915, 14672.
- **Hijau DENGAN CATATAN (patch LEBIH SEMPIT dari gold; tetap memperbaiki bug, divergen di
  sudut yang tak diuji test mana pun) — 2:** 13710, 13028.
- **Merah, akar HARNESS (bukan model) — 2:** 14580 (trace-injection gagal atas repro
  subprocess), 14752 (judge/LV-05 memaksa model membuang repro minimal-benar).
- **Kegagalan sisi-model MURNI: 0.** Di 14752 kelemahan eksekusi model nyata TAPI sekunder —
  ia muncul hanya SETELAH judge memaksa model meninggalkan checkpoint known-good-nya.
- **Lulus-palsu tipe file-salah (à la 13658): 0.** Kelima resolved punya `file_match=true`
  DAN `line_overlap=true`. (Ingat: recall detektor ini rendah — file_match=true bukan bukti
  benar; itulah kenapa §3b di bawah tetap dijalankan.)

### Per-case (ringkas; bukti di run dir yang disebut)

- **15347** (`f-dev--…--r1`, resolved, F2P 1/1, P2P 29/29). §3b **SETARA**: patch
  byte-identik gold — `if obj.extra_tags:` → `if obj.extra_tags is not None:` di
  `MessageEncoder.default` (`storage/cookie.py`). Repro (`r-dev--…--r1`) **K4 saja** (K1/
  K1-ketat/K2/K3/K5 semua TIDAK; vonis nilai eksak `== ""`, default mendarat FAIL).
  Under-general yang lolos: paksa `None→""` di sisi decode. **Contoh hijau-sahih yang
  dicapai TANPA bantuan yardstick** (mirip 14238/14382) — berguna sebagai baseline
  pembanding. LV-09 bersih. Perkuat: profil K4 dominan (predikat bagus pun tetap K4, seperti
  11179).
- **14915** (`f-dev--…--r1`, resolved, F2P 1/1 `test_choice_value_hash`, P2P 23/23). §3b
  **SETARA**: `def __hash__(self): return hash(self.value)` di `ModelChoiceIteratorValue`
  (`forms/models.py`), identik gold, tak bocor ke kelas generik. Repro **K1+K4+K5**,
  K1-ketat TIDAK (`except Exception`→FAIL menahan katastrofik). Under-general yang lolos:
  `return id(self)` — hashable → tak ada `TypeError` → PASS, tapi `mciv(1) in {1:…}` gagal
  cocok → `data-fields` diam-diam tak terpasang; repro buta karena tak assert `data-fields`
  (K4). **Hijau di sini benar hanya karena model menyalin fix minimal-benar, bukan karena
  yardstick** — perkuat LV-01.
- **14672** (`f-dev--…--r1`, resolved, F2P 169/169). §3b **SETARA**:
  `make_hashable(self.through_fields)` di `ManyToManyRel.identity`, identik gold. Repro
  **K1+K4+K5** (K2 versi BENAR: cabang tak-terduga di-`raise` ulang, bukan diam→PASS;
  K1-ketat TIDAK). Under-general yang lolos: `tuple(self.through_fields)`. Churn tinggi
  (5 retry; model sempat merusak file dengan import salah) lalu konvergen ke gold. LV-09
  bersih. **Kaveat yang layak masuk LV-14 (lihat di bawah): `swebench_spec.json` case ini
  `PASS_TO_PASS: []` kosong by-spec** (SWE-bench_Lite) — seluruh ~169 test masuk F2P karena
  `test_patch` mengubah `through_fields` Event jadi list → `TypeError` meruntuhkan `setUp`
  seluruh modul di base. Konsekuensi: **nol pagar regresi; "resolved" bersandar 100% pada
  F2P.** Aman di sini HANYA karena §3b SETARA — kalau patch bukan gold, false-green sangat
  mungkin lolos. **Untuk instance ber-P2P kosong, verifikasi §3b wajib; hijau swebench
  sendiri tidak cukup.**
- **13710** (`f-dev--…--r1`, resolved, F2P 1/1, P2P 62/62, file+line match). §3b **LEBIH
  SEMPIT (divergen gold)** — instansiasi **LV-14**. Gold menaruh blok `verbose_name_plural`
  SEBELUM defaulting `verbose_name` (memakai None-ness sebagai sinyal); model menaruhnya
  SESUDAH, sehingga `if self.verbose_name is not None:` SELALU True dan cabang
  `else: self.model._meta.verbose_name_plural` menjadi **DEAD CODE**. Akibat: model SELALU
  membentuk plural `format_lazy('{}s', verbose_name)` dan **tidak pernah menghormati**
  `Meta.verbose_name_plural` ireguler. Regresi konkret: inline tanpa nama pada model
  ber-`verbose_name_plural="children"` → "childs", bukan "children". Keempat sub-kasus F2P
  SEMUA menyetel `verbose_name` inline (jalur di mana model==gold) → tidak membedakan; 62
  P2P tidak menyentuh jalur bare-inline. Higiene: 3 file kosong (`fix_options.py`,
  `repro_app/*`) ikut di-commit; `gold_eval.touched_files` menyaringnya sehingga
  `file_match=true` bersifat murah hati. Repro **K4+K5** (vonis substring `"Custom Child
  Name" in plural`); under-general yang lolos: `verbose_name_plural = verbose_name` (tanpa
  "s") tetap PASS repro walau F2P resmi menolak. LV-09 bersih.
- **13028** (`f-dev--…--r1`, resolved, F2P 2/2, P2P 276/276, file+line match). §3b **LEBIH
  SEMPIT (under-general), fungsional-setara di domain teruji, BUKAN lulus-palsu.** Gold
  memakai prinsip `hasattr(expression,'resolve_expression')` (apakah ini ekspresi); model
  mengunci penanda insidental `not hasattr(expression,'_state')` (mengecualikan instance
  model). Bersinggungan-terbalik: sama di instance-model dan di ekspresi asli tak-filterable
  (itu sebabnya 276 P2P hijau), tetapi meninggalkan **lubang laten** — objek
  non-ekspresi-non-model ber-`filterable=False` → model RAISE, gold TIDAK (praktis tak ada
  di Django nyata). Repro **K1+K4+K5**, K1-ketat TIDAK (`except Exception`→`ERROR`, contoh
  BENAR di sisi K1-ketat). Under-general yang lolos: `def check_filterable(self, expression):
  return` (netralkan `raise` total) lolos repro DAN `test_field_with_filterable` (yang hanya
  `assertSequenceEqual([a3,a4])`). LV-09 bersih. Perkuat **LV-14 + LV-01**.
- **14580** — **MERAH di LOCALIZE, akar HARNESS. Ini temuan paling baru batch ini; dicatat
  sebagai bug-robustness, BUKAN lever gaming** (detail di sub-section terpisah di bawah).
  REPRODUCE-nya sendiri qualified dan repro-nya **NON-K4** (satu-satunya di batch ini) —
  lihat tally.
- **14752** — **MERAH di REPRODUCE, akar HARNESS (LV-05).** Perkuat LV-05/LV-06/LV-07/LV-10/
  LV-12; detail di bukti penguat masing-masing di bawah. Tidak menambah sampel Tabel A
  (tidak ada repro qualified).

### Bukti penguat yang ditambahkan ke entri lever (per case)

- **LV-01 (yardstick longgar):** +15347 (K4-saja, predikat nilai bagus tetap K4), +14915
  (K1+K4+K5, under-general `id(self)`), +14672 (K1+K4+K5, under-general `tuple()`), +13710
  (K4+K5, substring), +13028 (K1+K4+K5, `check_filterable: return`). **Lima kali berturut:
  hijau ≠ yardstick menggigit** — tiga di antaranya (15347, 14915, 14672) hijau-benar yang
  dicapai TANPA bantuan repro; dua (13710, 13028) hijau atas patch yang divergen dari gold.
- **LV-14 (isi patch-vs-gold tak dibandingkan):** +13710 (dead-code else → plural salah
  untuk model ber-plural ireguler; lolos F2P+P2P karena jalur tak diuji), +13028 (penanda
  `_state` insidental vs prinsip `resolve_expression`; lubang laten), +kaveat 14672 (P2P
  kosong by-spec → nol pagar regresi; §3b wajib).
- **LV-05 (judge menahan bukti yang sudah disaksikan):** +14752 — di r1 **dan** r3 driver
  menyimpan checkpoint known-good `repro-first-fail.py` = in-process
  `hasattr(AutocompleteJsonView,'serialize_result')` → base FAIL; karena gold **menambah**
  method itu, flip base→gold PASS praktis dijamin. Judge menolak: r1 murni **`correctness`**
  ("test the observable / follow the user's action path"), r3 campuran
  (`correctness` + `pipe_runtime`/action-path `mechanics`). Model pivot ke orkestrasi
  admin+HTTP+login → **3 run habis-budget, nol qualified**. **LV-05(b) mekanika-saja TIDAK
  menyelamatkan r1 dan hanya separuh r3** → menguatkan **LV-13(a)** (kewajiban bukti >
  filter kategori); pola persis 13230. Ini bukti paling telak sejauh ini bahwa penolakan
  judge memindahkan run dari desain-terbukti-lolos ke desain-tak-teruji yang gagal total,
  dan case wall-clock terpanjang di korpus REPRODUCE (r1 1495s / r2 1339s / r3 2244s
  ≈ 84 menit).
- **LV-06 (`App` one-shot / ready-line):** +14752 r3 — **5×** `app failed to become ready
  (30s)` pada `runserver` model, plus dua halusinasi API (`django.apps.Applicationcstdlib`,
  `Apps.register_app`).
- **LV-07 / LV-10 (mislabel `wrong-logic`/"gold-unsatisfiable"):** +14752 r3 — flip
  base=FAIL/patched=FAIL divonis `wrong-logic`/"gold-unsatisfiable predicate" padahal sebab
  riil = **CSRF 403**: `session.post('/admin/login/')` tanpa `csrfmiddlewaretoken`
  (`gate_runs.json`: base & patched dua-duanya `Login failed with status 403`), sehingga
  jalur autocomplete tak pernah tercapai di kedua dunia. Kemunculan lain "environment repro
  rusak → dibaca sebagai predikat model salah".
- **LV-12 (preferensikan repro in-process):** +14752 — checkpoint model = in-process
  `hasattr` (nol orkestrasi, akan flip); setelah ditolak judge model membangun full-project +
  `runserver` + login HTTP → titik gagal berlipat (path, migrasi, kesiapan server, CSRF,
  JSONDecode) dan **~59 kejadian `ModuleNotFoundError` scaffolding** lintas 3 run. Bukti
  langsung tesis LV-12; sub-flavor baru: di sini titik-gagal-tak-terkait-bug = **langkah
  autentikasi**, bukan predikat/URLconf.

### Temuan bug-robustness harness (BARU) — django-14580: trace-injection gagal atas repro subprocess

**Ini bukan lever gaming dan sengaja TIDAK diberi nomor LV** (bar tinggi, katalog jenuh untuk
kelas gaming; dan aturan main "jangan namai kelas baru terlalu cepat"). Dicatat di sini
sebagai bug-robustness + gap kontrak lintas-fase, dengan syarat kapan boleh naik jadi entri.

- **Gejala:** LOCALIZE gagal **3/3 rerun deterministik**. `verdict.json` tiap run
  `pass_l1=false`, verdict `syntax-fail`, `failures=["artefak wajib tidak ada:
  localize.md"]`. `files/` KOSONG total ketiga run — model **tidak pernah dipanggil**.
- **Akar (dari `console.log`/`events.jsonl` `l-dev--django__django-14580--r1..r3`):** driver
  LOCALIZE menjalankan repro input **di bawah trace** untuk membangun "trace pool" (file
  repository yang disentuh repro) sebagai benih lokalisasi. Repro 14580 menjalankan seluruh
  kode Django lewat `subprocess.run([sys.executable, manage.py, ...])`, jadi proses parent
  yang di-trace **tidak pernah** meng-import/mengeksekusi satu pun file `/testbed/django/…`
  (semua kode repo jalan di proses ANAK). → event `abort` (`why: "trace pool is empty — no
  traced process executed a repository file"`) → stage abort **SEBELUM** LLM → `localize.md`
  tak pernah ada. "localize.md not found" adalah **gejala hilir**, bukan sebab.
- **Klasifikasi tegas:** kegagalan **HARNESS**, bukan model (model tak jalan), bukan
  eval-penamaan (gate PRODUK yang gagal, `pass_l1=false`), bukan mismatch nama-file (`files/`
  kosong). Deterministik → retry 3× mustahil lolos.
- **Gap kontrak lintas-fase:** kualifikasi REPRODUCE (flip OK) **tidak menjamin** repro bisa
  di-trace di LOCALIZE. Berbagi akar (repro berbentuk subprocess) dengan **LV-12** — bisa
  dibaca sebagai konsekuensi hilir LV-12 yang belum tercatat: repro subprocess bukan hanya
  membakar turn (LV-06) dan menyeret titik gagal (LV-12), ia **mematikan fase LOCALIZE
  sepenuhnya**.
- **Syarat naik jadi entri lever:** kalau sweep menunjukkan ≥3 case lain dengan repro
  qualified berbentuk subprocess yang juga menggugurkan LOCALIZE via trace-pool-kosong, maka
  *"gate REPRODUCE wajib menolak repro yang tidak mengeksekusi file repo in-process"* (atau
  *"trace-injection L mengikuti fork ke subprocess anak"*) layak jadi entri mekanis. Sekarang
  **n=1**; dicatat sebagai bug-robustness dulu. Rekomendasi (JANGAN eksekusi): trace juga
  subprocess anak (follow-fork / `sitecustomize` `settrace`), ATAU gate R menambah cek
  "repro mengeksekusi file repository in-process" sebagai syarat handoff ke L.
- **Repro qualified 14580 sendiri** (`r-dev--…--r1`, flip terverifikasi FAIL@base/PASS@gold):
  **NON-K4** (diskriminasi asli + flip verified — satu-satunya NON-K4 di batch bot-02),
  K1+K5(substring-ketat pesan error persis), K1-ketat YA-PARSIAL (hanya cabang `migrate`:
  error lain → PASS; langkah `makemigrations` dijaga `sys.exit(1)`), K2 YA-wajar. LV-09
  bersih.

### Pembaruan Tabel frekuensi bertanggal 2026-07-21 (bot-02) — 6 case baru ber-repro-qualified

**Denominator.** Sampel Tabel A naik **27 → 33 case** (+6: 13710, 13028, 14672, 14915,
15347, 14580; tiap satu punya repro qualified yang belum pernah masuk hitungan). **14752
TIDAK menambah** (nol repro qualified). `r-dev` delta batch ini: **+9 run** (6 qualified di 6
case baru + 3 non-qualified dari 14752 r1/r2/r3). Sampel `f-dev` **+5 run** (kelima resolved;
14580 tak punya f-dev karena berhenti di L, 14752 tak punya karena berhenti di R).

**Klasifikasi 6 repro baru** (manual, metode sama):

- **13710** — K1 T, K1-ketat T, K2 T, K3 T, **K4 Y**, **K5 Y** (substring).
- **13028** — K1 Y, K1-ketat T (`except`→ERROR), K2 T, K3 T, **K4 Y**, **K5 Y**.
- **14672** — K1 Y, K1-ketat T, **K2 Y (BENAR** — cabang re-raise), K3 T, **K4 Y**, **K5 Y**.
- **14915** — K1 Y, K1-ketat T, K2 T (cabang tak-terjangkau), K3 T, **K4 Y**, **K5 Y**.
- **15347** — K1 T, K1-ketat T, K2 T, K3 T, **K4 Y**, K5 T (vonis nilai eksak).
- **14580** — K1 Y, **K1-ketat Y (parsial**, cabang `migrate` saja), **K2 Y (wajar)**, K3 T,
  **K4 TIDAK** (diskriminasi asli + flip verified), K5 Y (substring-ketat).

**Hitungan K1–K5 diperbarui (denominator 33 case, satu repro qualified per case):**

- **K1: 16 dari 33** (48%). Naik empat: +13028, +14672, +14915, +14580.
- **K1-ketat: 5 dari 33** (15%). Naik satu: **+14580** (parsial — hanya cabang `migrate`
  yang meloloskan error tak-terkait ke PASS; `makemigrations` dijaga). Daftar kini 11039,
  11910, 12286, 14238, 14580. Proporsi tetap minoritas — **KH-05 tidak terbantah**.
- **K2: 11 dari 33**. Naik dua: +14672, +14580 — **dua-duanya subset "K2 karena repro
  berlaku jujur"**, sehingga subset-benar naik dari **4/9 → 6/11** (14672 re-raise cabang
  tak-terduga; 14580 menahan status saat setup `makemigrations` gagal). K2 makin jelas
  **bukan metrik cacat**.
- **K3: 4 dari 33**. Tidak berubah (nol dari enam repro baru mengimpor `pipe_runtime`).
  Kelas ini tetap tidak menyebar.
- **K4: 27 dari 33** (82%). Naik lima (+13710, 13028, 14672, 14915, 15347); **14580 NON-K4**.
  **Tetap kriteria dengan prevalensi tertinggi.** Yang **punya** kontrol positif kini 6:
  10914, 11422 r44, 13768 r4, 14017, 14382 r2, **14580** (kontrol jenis flip — repro
  membedakan base vs gold via string error spesifik).
- **K5: 20 dari 33** (61%). Naik lima (+13710, 13028, 14672, 14915, 14580; **15347 TIDAK** —
  vonis nilai eksak `== ""`).
- **Irisan K4 ∧ K5: 16 dari 33** (48%). Naik empat (13710, 13028, 14672, 14915; 15347 K4
  tanpa K5, 14580 K5 tanpa K4). **Tetap profil kelemahan yardstick yang sebenarnya.**

**Pembacaan yang searah dengan sesi bot-01, tidak membalik apa pun.** Enam repro baru
menambah bukti bahwa **K4 (kontrol positif absen) adalah sumbu dominan**, dan bahwa **kualitas
predikat lepas dari kontrol**: 15347 punya predikat nilai terbaik di batch (K5 TIDAK) dan
tetap K4; 14580 justru satu-satunya yang punya kontrol (jenis flip) dan predikatnya K5. Ini
mengulang pemisahan yang sudah dicatat lewat 11179 dan trio 14382/14238/13590.

**Tabel B — increment dari 14752** (regex atas `detail.why` `events.jsonl` r1/r2/r3):

- **Repro scaffolding gagal `ModuleNotFoundError` (bentuk orkestrasi, LV-12):** +14752 —
  **~59 kejadian lintas 3 run** (`app`/`project`/`repro_app`); ketiga run habis-budget tanpa
  qualified. Case wall-clock terpanjang & terboros di korpus REPRODUCE (≈84 menit).
- **`App` gagal ready (LV-06):** +14752 r3, **5×** `app failed to become ready (30s)`.
- **Penolakan judge menahan DONE (LV-05):** +14752, **2 run** (r1, r3). (Delta saja — matcher
  angka basis tabel lama belum dipastikan; lihat peringatan bot-01 sesi ketiga.)
- **Baris baru — `REPRO_STATUS`/flip mislabel karena langkah AUTH rusak (LV-07/LV-10):**
  +14752 r3 (CSRF 403). Bentuk kedelapan-plus "environment repro rusak dibaca sebagai
  predikat salah".

**Tabel C (LV-09) — `grep -c "No module named 'pipe_runtime'"` atas 5 `console.log` `f-dev`
baru:** kelima **0**. Kelompok **bersih** naik +5 run/+5 case (13710, 13028, 14672, 14915,
15347), **kelima `resolved=true`**. Kelompok **terpapar TIDAK BERUBAH** (5 run, 3 case, 1
dari 5). Confounder lama tetap berlaku; rasio tetap **tidak boleh dibaca kausal**.

**Tabel D (OFF-GOLD) — sweep 5 `f-dev` baru** (semua punya `swebench_eval.json` DAN
`gold_eval.json`): **`resolved=true` 5 dari 5** (13710, 13028, 14672, 14915, 15347);
**`resolved=true` DAN `file_match=false`: 0 dari 5** — hit korpus tetap **hanya 13658**.
`line_overlap=false`: 0. Jadi denominator `f-dev` ber-kedua-file naik ke **20 run**;
`resolved=true` **15 dari 20**; `resolved=true & file_match=false` **tetap 1** (13658),
kini **1 dari 15 run `resolved=true`**. **Peringatan recall-rendah lama tetap berlaku
sepenuhnya** — dua hijau-dengan-catatan batch ini (13710, 13028) dua-duanya `file_match=true`
dan **tidak tersentuh** metrik ini, persis seperti 12915/12286. Metrik ini menghitung
kemunculan sinyal, bukan frekuensi lulus-palsu.

### Kenapa sabotase §3d tidak dieksekusi di batch ini (dan apa yang direkomendasikan)

Tiga subagent merekomendasikan sabotase (13710, 13028, 14672) untuk membuktikan repro
under-diskriminatif secara empiris. **Tidak dieksekusi**, dengan alasan yang dinyatakan jujur
supaya bisa dinilai ulang:

1. Untuk 13710 divergensinya **struktural dan tak-ambigu** (dead-code `else` terbaca langsung
   dari `fix.diff`), dan kelonggaran repro-nya **sudah terbukti oleh hasil `resolved=true`
   itu sendiri** — repro meloloskan patch model yang divergen-dari-gold. Menjalankan probe
   hanya menambah satu titik ke kelas **K4∧K5 yang sudah jenuh** (16/33), bukan menemukan hal
   baru.
2. Untuk 13028 divergensinya laten/kontrived (butuh objek non-ekspresi-non-model yang praktis
   tak ada di Django nyata); nilai probe rendah relatif ongkos + risiko jebakan §3d
   (interpreter testbed, bytecode basi).
3. Untuk 14672 patchnya **SETARA gold**, jadi sabotase di sana bukan tentang kebenaran patch
   melainkan tentang P2P-kosong — sudah dinyatakan cukup lewat pembacaan `swebench_spec.json`.

**Rekomendasi yang dicatat untuk diangkat bila kelak ada yang menjalankan sabotase
sistematis:** (a) 13710 — pasang `verbose_name_plural = verbose_name` (tanpa "s"); prediksi
frozen repro tetap PASS, F2P resmi FAIL. (b) 13028 — pasang `check_filterable: return`;
prediksi repro PASS DAN F2P PASS (repro dan test resmi sama-sama tak menegaskan ekspresi
tak-filterable harus tetap ditolak — ini kontrol positif yang hilang). Keduanya menyasar
**kelemahan repro**, bukan menuduh patch salah.

---

## Catatan penutup autopsi batch bot-03 (2026-07-21) — estafet 22-case, bagian 7 (3 django + 4 astropy)

**Korpus:** 7 case dijalankan RLFV penuh lewat `scripts/run_rlfv_batch.py`
(`django__django-15789, 15814, 15851, astropy__astropy-12907, 14365, 14995, 6938`), state
`artifacts/batch-bot03.json`. Model `google/gemma-4-31B-it`. **4 case astropy = base non-django
PERTAMA di korpus** (sebelumnya 100% django). Autopsi tiap case oleh satu subagent read-only
(izin eksplisit membantah pemanggil, SOP §6a); integrasi (tulisan ini) serial oleh bot-03.
Metode klasifikasi K1–K5 = manual, satu repro qualified per case, konsisten dengan 33 file
sebelumnya. **Sabotase §3d DIEKSEKUSI untuk 12907 dan 14365** (dua case yang vonisnya bergeser
oleh eksperimen) — kontras dengan bot-02 yang tidak menjalankan sabotase; alasan per-case di
bawah.

**Papan skor akhir: resolved=3/7.** Tiga case gagal di REPRODUCE/FIX bukan karena laju hijau
rendah semata — dua di antaranya membawa temuan akar-harness.

### Papan skor yang membedakan (bukan angka agregat)

- **Hijau ASLI (patch SETARA gold secara semantik) — 1:** 6938.
- **Hijau DENGAN CATATAN (patch memperbaiki bug tapi LEBIH LONGGAR/divergen dari gold di sudut
  tak-teruji) — 2:** 15814 (over-select: `only()` diam-diam tak dihormati untuk relasi proxy),
  14995 (aliasing: `deepcopy` dibuang, mask dikembalikan by-reference).
- **Merah di FIX, akar-MODEL pada patch + akar-METODOLOGI pada repro (LV-01) — 2:** 12907
  (patch over-broad me-rewrite modul & menghapus API publik `is_separable` → ImportError
  collection → 15 test error serempak), 14365 (patch SUBSET: 1 dari 2 hunk gold, hunk kedua
  `v.upper()=="NO"` hilang → F2P gagal deterministik).
- **Merah di REPRODUCE — 2, akar BERBEDA:** 15789 (akar-MODEL: penukaran urutan argumen
  `json_script` → repro logis-benar tapi gagal flip), 15851 (akar-HARNESS: model tak pernah
  menulis repro; loop tool-call-token 40 turn ×3, verdict `syntax-fail` salah-label).
- **Kegagalan sisi-model MURNI yang "bersih": 1** (15789 — arg-swap; sisanya bercampur akar).
- **Lulus-palsu tipe file-salah (à la 13658): 0.** Ketiga resolved (15814, 14995, 6938)
  `file_match=true` DAN `line_overlap=true`. (Recall detektor rendah — §3b tetap dijalankan;
  dan dua hijau-dengan-catatan lolos justru karena §3b, bukan gold_eval.)

### Per-case (ringkas; bukti di run dir yang disebut)

- **6938** (`f-dev--…--r1`, resolved, F2P 2/2, P2P 11/11, file+line match). §3b **SETARA**:
  `output_field[:] = output_field.replace(encode_ascii('E'), encode_ascii('D'))` vs gold
  `replace(b'E', b'D')`; `encode_ascii(s)=s.encode('ascii')` → byte-identik; inti fix
  (in-place slice atas bytes immutable) identik. Repro r2 **K4∧K5** (vonis kehadiran substring
  byte `b'D+'`, tak baca-balik nilai). Under-general yang lolos: hapus guard `if 'D' in format:`
  (repro 1-kolom D, tak ada E-format legit terlihat rusak). **Hijau-asli TANPA bantuan
  yardstick** (mirip 15347/14238). Kelas menarik di r1 (mock-churn) → **kandidat-ditolak**
  (lihat di bawah). LV-09 bersih.
- **14995** (`f-dev--…--r1`, resolved, F2P 1/1 `test_nddata_bitmask_arithmetic`, P2P 179/179,
  file+line match). §3b **LEBIH LONGGAR (divergen gold, tak lulus-palsu)**: gold 1-hunk
  `elif operand is None:` → `elif operand.mask is None:`; model rewrite `_arithmetic_mask` jadi
  guard 4-cabang, **value-equivalent di semua jalur teruji** TAPI (a) mengembalikan mask
  by-reference alih-alih `return deepcopy(...)` gold (komentar gold: *"so there is no reference
  in the result"*) → **aliasing** yang tak satu pun dari 180 test mengukur (semua `assert_equal`
  nilai) — tanda tangan **LV-14**, sekelas 12915; (b) cabang `first_found` = dead code. Repro
  **K1+K4** (`_ = res1.mask` dibuang; PASS = "tak ada TypeError"). Under-general yang lolos:
  `elif operand.mask is None: return None` — repro PASS, F2P resmi FAIL. LV-09 bersih.
- **15814** (`f-dev--…--r1`, resolved, F2P 1/1 `test_select_related_only`, P2P 29/29, file+line
  match). §3b **LEBIH LONGGAR (divergen gold)**: di `deferred_to_data` (~751) gold menyetel
  `cur_model = cur_model._meta.concrete_model` (concrete); model menulis
  `opts = cur_model._meta.concrete_model._meta` sehingga `cur_model` **tetap PROXY** dan
  dipakai sebagai key `must_include`/`seen`, sedang konsumen di `compiler.py` mencari dengan
  key **concrete** → restriksi `only()` tak diterapkan pada relasi proxy → **semua kolom dimuat**
  (crash hilang lewat over-select, bukan pk tepat). **Probe (probe15814, testbed interp):** gold
  → `get_deferred_fields()=['age']`, 3 kolom SQL; model → `[]`, 4 kolom. **Baris fix model =
  saran reporter verbatim di problem statement (baris 51-52); maintainer sengaja memilih varian
  lebih ketat** (`cur_model`, hanya di `hints_text` yang model tak lihat) — jadi hijau-dengan-
  catatan muncul di case **tier-1 "fix verbatim"** justru karena baris verbatim itu under-general.
  **Kedua yardstick BUTA:** F2P resmi hanya `assert qs.get()==issue` (by-pk), tak cek deferred
  fields. Repro **K1+K1-ketat+K4+K5** (`except ValueError 'id'…→FAIL`, semua cabang lain→PASS).
- **12907** (`f-dev--…--r1`, **resolved=FALSE**, F2P 0/2, P2P 0/13, `file_match=true`,
  `line_overlap=false`). §3b **OVER-BROAD (akar-model)**: gold = **1 baris** di `_cstack`
  (`cright[...] = 1` → `= right`); model **menemukan fix inti benar** (`= right` hadir) tapi
  me-**rewrite seluruh modul** dan **menghapus `is_separable`** (ada di `__all__`, diimpor di
  kepala `test_separable.py`) → `ImportError: cannot import name 'is_separable'` →
  **`collected 0 items / 2 errors`** → 15 test (2 F2P + 13 P2P) error **serempak di collection**,
  bukan 13 kegagalan-nilai individual. **`line_overlap=false` MENYESATKAN**: baris fix gold ada
  & benar; overlap hilang karena rewrite menggeser penomoran baris (lihat KH-13). Repro
  **K1+K2+K4** (impor hanya `separability_matrix`, cek satu off-diagonal `==True`, nol kontrol
  positif). **Sabotase (probe12907, testbed interp):** baseline FAIL → gold PASS → gold+`_cdot`
  raise (operator `|` tak dipakai repro) **PASS** → gold+`separability_matrix` return float
  **PASS**. Repro buta terhadap kelas kerusakan yang justru dieksekusi test resmi.
- **14365** (`f-dev--…--r1`, **resolved=FALSE**, F2P 0/1 `test_qdp.py::test_roundtrip[True]`,
  P2P 8/8, `file_match=true`, `line_overlap=true`). §3b **SUBSET KETAT**: gold 2 hunk (hunk-1
  `re.IGNORECASE` di `_line_type`; hunk-2 `if v.upper()=="NO":` di `_get_tables_from_qdp_file`);
  model **hanya hunk-1**, hunk-2 hilang. `line_overlap=true` benar tapi menyesatkan — cocok
  hanya karena hunk-1 menindih baris gold; metrik berhenti di lokasi, tak lihat hunk-2 absen.
  **Sabotase/flaky-test (probe14365, testbed interp):** gold **3/3 PASS**, model **3/3 FAIL**,
  error identik tiap kali (`could not convert string to float: 'no'` @ qdp.py:316) — **noise-prone
  TERBANTAH, test deterministik**; pergeseran lokasi crash baseline:78 → model:316 = bukti kausal
  hunk-1 lolos, mati di titik hunk-2. Repro **K4+K5** (data uji tanpa `no` lowercase → hunk-2 tak
  teruji; §3c(a) under-coverage). LV-09 bersih.
- **15789** (`r-dev--…--r1/r2/r3`, REPRODUCE tidak qualified, `wrong-logic` 3/3). Akar-MODEL
  murni. Signature `json_script(value, element_id=None, encoder=None)`; model memanggil
  `json_script("my-id", data, encoder=…)` → argumen tertukar, encoder men-serialize string id
  bukan set → predikat tak menyentuh jalur gold. **Probe (probe15789):** gold + panggilan model
  apa adanya → FAIL (reproduksi vonis `patched:FAIL`); gold + urutan argumen dibetulkan → PASS.
  **Nol retry** ketiga run (model yakin; pre-check gold-blind hanya verifikasi base FAIL, tak bisa
  lihat flip-fail). Tak menambah Tabel A (tak ada repro qualified). LV-05/06/09 semua NEGATIF;
  gate flip bekerja benar (menolak repro takkan flip).
- **15851** (`r-dev--…--r1/r2/r3`, REPRODUCE tidak qualified, `syntax-fail` 3/3). **Akar-HARNESS
  primer.** `syntax-fail` **BUKAN SyntaxError** — model **tak pernah menulis repro.py**; `files/`
  ketiga run hanya berisi `pipe_runtime.py`. Ketiga run terjebak loop degeneratif meng-emit token
  `<|tool_call|>` sendiri **tanpa fenced-block**, `parse_actions`→0 aksi, byte-identik 40 turn ×3
  (temp 0.0). Verdict `syntax-fail` (`run_repro_gates.py:65-68` "required artifacts missing")
  me-relabel "artefak tak diproduksi". Detail + kandidat mekanis di **temuan observability (B)**.

### Bukti penguat yang ditambahkan ke entri lever (per case)

- **LV-01 (yardstick longgar):** +6938 (K4∧K5, under-general hapus guard format), +14995
  (K1+K4, under-general `return None`), +15814 (K1+K1-ketat+K4+K5, under-general over-select),
  +12907 (K1+K2+K4, sabotase 2/2 PASS), +14365 (K4+K5 under-coverage). **Nilai marjinal
  terpenting: kelima adalah instans NON-DJANGO pertama, dan tanda tangan LV-01 SAMA PERSIS di
  luar django** → kelemahan yardstick adalah **struktural pada product harness**, bukan artefak
  korpus django. Dua hijau (15814, 14995) + satu merah (14365) menegaskan "HIJAU/lokasi-benar
  tak membuktikan yardstick"; 15814 menambah kasus di mana **test resmi F2P pun ikut buta**
  (sejajar §4 12915/12286/13658).
- **LV-01 sub-lubang baru (dari 12907) — cakupan permukaan publik:** semua bukti LV-01 django
  menang lewat nilai-test-salah/regresi-diam; 12907 menang lewat **ImportError di collection**
  karena repro **tak mengimpor simbol publik yang dihapus** (`is_separable`). Isi konkret
  tambahan untuk LV-01: *repro sebaiknya mengimpor & melatih SELURUH permukaan publik yang
  disentuh/berdampingan gold, bukan hanya fungsi target.* (Gold-blind: nama simbol publik ada
  di modul, bukan di gold.)
- **LV-14 (isi patch-vs-gold tak dibandingkan):** +14995 (aliasing: `deepcopy` dibuang → mask
  by-reference; tak terukur test mana pun), +14365 (**subset-hunk**: gold 2 region, model 1),
  +12907 (rewrite → `line_overlap=false` false-negative). **Detektor termurah baru (dari 14365):
  hitung jumlah region hunk gold vs patch; mismatch region SEKALIGUS `line_overlap=true` = sinyal
  subset yang murah & mekanis**, tak butuh diff simbol seperti 12286.
- **Kandidat-ditolak — "mock-churn astropy" (dari 6938 r1):** r1 habis 40 msg/8 attempt karena
  model membangun objek FITS palsu (`MockColDefs not subscriptable`, `MockFormat not iterable`,
  halusinasi `ImportError _AsciiColDefs/ColDef`) alih-alih `fits.TableHDU`+`np.rec.array` nyata;
  r2 self-recover pakai objek nyata. **DITOLAK sebagai entri** — akar-model, self-recover, n=1,
  tak mengikat verdict (hasil akhir hijau-asli). Syarat naik: ≥ beberapa case pustaka-saintifik
  (astropy/numpy) dengan tanda-tangan mock-churn sama DAN ada bentuk mekanis (hint "pakai objek
  nyata via API publik" = tambah-kalimat-prompt, prioritas rendah aturan #7).

### Temuan BARU (bug-robustness) — dicatat, TIDAK diberi nomor LV (bar tinggi, katalog jenuh)

**(A) `swebench_checker` crash `charmap` di Windows atas output test astropy — realm EVAL.**

- **Gejala (deterministik):** 3 dari 4 case astropy (12907, 14365, 14995) — `swebench_checker`
  exit 1 dengan `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81`; `swebench_eval.json`
  **tidak ditulis** (vonis resmi hilang). Django & astropy-6938 tidak terkena (output test-nya
  kebetulan cp1252-safe).
- **Akar:** `eval/swebench_checker.py:141` menulis log dengan `encoding="utf-8"`, lalu baris 142
  `grade_log` → swebench `get_eval_report(str(log_path))` **membaca ulang log tanpa `encoding=`**
  → Windows memakai `cp1252` default → mati pada byte non-cp1252 di output test astropy. Mismatch
  tulis-UTF-8 / baca-cp1252. `except Exception` (baris 147) menelannya sehingga
  `swebench_eval.json` sengaja tak ditulis (desain: jangan tulis vonis yang tak tercapai) — benar
  sebagai kebijakan, tetapi menyembunyikan bahwa **sebabnya lingkungan, bukan grading**.
- **Klasifikasi:** akar-ENVIRONMENT/harness di realm eval (bukan product R→L→F, jadi di luar
  cakupan LV-01..LV-14). Deterministik & mekanis → keyakinan lebih tinggi dari n=1 biasa.
- **Cara vonis diperoleh (dicatat demi transparansi):** ketiga checker di-**re-run di bawah
  `PYTHONUTF8=1`** (flag interpreter, memaksa `open()` default UTF-8) — **tanpa mengubah kode
  harness**, tanpa rename/hapus run dir; `swebench_eval.json` yang hilang lalu terisi. Ini higiene
  interpreter, sekelas "pakai interpreter testbed / hapus bytecode basi" (SOP §3d), bukan
  penerapan lever. Hasil: 12907 resolved=false, 14365 resolved=false, 14995 resolved=true.
- **Rekomendasi (JANGAN eksekusi):** `get_eval_report` dipanggil dengan log yang dibaca eksplisit
  `encoding="utf-8"`, ATAU harness men-set `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8` untuk subproses
  eval. **Syarat naik jadi entri lever bernomor:** bila base non-ASCII lain (numpy/scipy/dll) juga
  memicunya — yang praktis pasti, karena sebabnya default-encoding platform, bukan astropy.

**(B) Verdict REPRODUCE `syntax-fail`/`wrong-logic` = bucket catch-all yang menyesatkan autopsi —
observability.**

- **Gejala:** label verdict menyatukan sebab yang berbeda dan **langsung menyebabkan misdiagnosa
  pemanggil di batch ini** (dua read-awal bot-03 terbantah karena percaya label; lihat KH-11/KH-12):
  - `syntax-fail` (`run_repro_gates.py:65-68` "required artifacts missing") menyatukan ≥3 kondisi,
    **nol di antaranya SyntaxError**: (i) model tak pernah menulis repro (15851 ×3, loop tool-call-
    token); (ii) budget habis oleh mock-churn (astropy-6938 r1); (iii) `REPRO_STATUS token not
    found` / `repro.md missing slots`. Distinct case yang menyentuh "artefak tak diproduksi" =
    **5 dari 45** (astropy-6938, django-11422/11797/14752/15851); **15851 satu-satunya gagal-total
    3/3** karena ini.
  - `wrong-logic`/"gold-unsatisfiable predicate" (kandidat-ditolak #3 LV-10, ~41 run) menyatukan
    ≥3 sub-sebab: setup tak lengkap (14382/11039), environment repro rusak dibaca predikat-salah
    (14752/CSRF-403), dan **sub-sebab BARU dari 15789: pemetaan argumen API yang salah** (repro
    logis-benar, gagal flip hanya karena urutan argumen tertukar).
- **Akar (15851, akar-harness):** `format_reminder()` (`run_reproduce_gemma.py:471-479`, yang
  menjelaskan bentuk ```bash benar) hanya dikirim bila `has_fences=True`; mode kegagalan
  token-`<|tool_call|>`-tanpa-fence justru dapat pesan generik terlemah. `next_step_nudge`
  (pemutus loop) hanya menyala bila `observed_fail=True`. Temp 0.0 → regenerasi byte-identik →
  40 turn terbakar 3×. Signature `<|tool_call|>` ini persis yang melahirkan `format_reminder`
  (docstring: "r11 11422") → **instansi kedua kelas yang sudah dikenal**, bukan kelas baru.
- **Kandidat mekanis (JANGAN eksekusi; urut nilai):**
  1. **Split verdict bucket** (nyaris gratis): `run_repro_gates` beri label sendiri
     (`no-artifact` vs `syntax-fail` yang sungguh SyntaxError). Persis defek observability yang
     menyesatkan batch ini. Sekaligus pisah bucket `wrong-logic` per sub-sebab (via `flip_run.json`).
  2. **Generalisasi `format_reminder`** agar menyala saat `has_fences=false` bila reply memuat
     penanda tool-call model (`<|tool_call|>`/`call:bash`).
  3. **Pemutus loop no-progress** lepas dari `observed_fail`: abort/eskalasi setelah K reply
     (near-)identik atau K turn tanpa repro.py.
- **Syarat naik jadi entri:** #1 nyaris gratis & berdampak langsung ke kualitas autopsi berikutnya;
  #2/#3 mekanis tapi menyentuh penalaran loop — angkat bila token-loop kambuh setelah #1 terpasang
  atau denominator gagal-total melebar (>1 case).

### Pembaruan Tabel frekuensi (bot-03, 2026-07-21) — 5 case baru ber-repro-qualified

**Denominator.** Sampel Tabel A naik **33 → 38 case** (+5: 15814, 12907, 14365, 14995, 6938;
masing-masing punya repro qualified baru). **15789 & 15851 TIDAK menambah** (tak ada repro
qualified). `r-dev` delta: +11 run (5 qualified + 6 non-qualified: 15789 r1-r3 `wrong-logic`,
15851 r1-r3 `syntax-fail`). Sampel `f-dev` **+5 run** (15814/12907/14365/14995/6938; 15789 &
15851 berhenti di R).

**Klasifikasi 5 repro baru** (manual, metode sama):

- **15814** — K1 Y, **K1-ketat Y** (cabang error non-target → PASS), K2 T, K3 T, **K4 Y**, **K5 Y**.
- **12907** — K1 Y, K1-ketat T (crash → tanpa `REPRO_STATUS`, tak mendarat PASS), **K2 Y**, K3 T,
  **K4 Y**, K5 T (vonis perbandingan nilai off-diagonal, bukan substring).
- **14365** — K1 T (polaritas aman, exception→FAIL), K1-ketat T, K2 T, K3 T, **K4 Y**, **K5 Y**.
- **14995** — K1 Y, K1-ketat T (`except`→FAIL), K2 T, K3 T, **K4 Y**, **K5 Y**.
- **6938** — K1 T (polaritas sehat, PASS menuntut `b'D'` hadir), K1-ketat T, K2 T, K3 T, **K4 Y**,
  **K5 Y**.

**Hitungan K1–K5 diperbarui (denominator 38 case, satu repro qualified per case):**

- **K1: 19 dari 38** (50%). Naik tiga: +15814, +12907, +14995.
- **K1-ketat: 6 dari 38** (16%). Naik satu: **+15814**. Daftar kini 11039, 11910, 12286, 14238,
  14580, 15814. Proporsi tetap minoritas — **KH-05 tetap tidak terbantah**.
- **K2: 12 dari 38**. Naik satu: +12907 (cabang crash tanpa `REPRO_STATUS`).
- **K3: 4 dari 38**. Tidak berubah (nol dari lima repro baru mengimpor `pipe_runtime`; keempat
  astropy in-process bersih). Kelas ini tetap tidak menyebar, **kini terkonfirmasi lintas-repo**.
- **K4: 32 dari 38** (84%). Naik lima (**kelima repro baru K4**). **Tetap kriteria prevalensi
  tertinggi**, dan kini terbukti dominan **di luar django juga**. Yang punya kontrol positif tetap
  6 (10914, 11422 r44, 13768 r4, 14017, 14382 r2, 14580) — nol dari batch ini.
- **K5: 24 dari 38** (63%). Naik empat (+15814, 14365, 14995, 6938; **12907 TIDAK** — vonis nilai).
- **Irisan K4 ∧ K5: 20 dari 38** (53%). Naik empat (15814, 14365, 14995, 6938; 12907 K4 tanpa K5).
  **Tetap profil kelemahan yardstick yang sebenarnya**, kini > separuh korpus.

**Pembacaan yang searah, tidak membalik apa pun.** Lima repro non-django menambah bukti bahwa
**K4 (kontrol positif absen) adalah sumbu dominan lintas-repo** (32/38, 84%), dan bahwa **kualitas
predikat lepas dari kontrol** (12907 punya predikat nilai, K5 TIDAK, tetap K4). Urutan pemasangan
yang disarankan tidak berubah; kontrol positif (K4) tetap kandidat isi konkret pertama LV-01.

**Tabel D (OFF-GOLD) — sweep 5 `f-dev` baru** (semua punya `swebench_eval.json` DAN `gold_eval.json`):
`resolved=true` **3 dari 5** (15814, 14995, 6938); **`resolved=true` DAN `file_match=false`: 0** —
hit korpus tetap **hanya 13658**. Denominator `f-dev` ber-kedua-file naik ke **25 run**;
`resolved=true` **18 dari 25**; `resolved=true & file_match=false` **tetap 1** (13658), kini
**1 dari 18**. **Sel baru yang layak dicatat: 12907 = `resolved=false` + `file_match=true` +
`line_overlap=false`** — kasus pertama di korpus di mana `line_overlap=false` muncul PADAHAL baris
fix benar hadir (artefak rewrite; lihat KH-13). Peringatan recall-rendah tetap berlaku penuh —
dua hijau-dengan-catatan batch ini (15814, 14995) dua-duanya `file_match=true`+`line_overlap=true`
dan **tidak tersentuh** metrik ini, persis pola 12915/12286.

### Kenapa sabotase §3d DIEKSEKUSI di batch ini (kontras bot-02)

bot-02 tidak menjalankan sabotase (divergensi struktural terbaca dari diff). bot-03 menjalankannya
untuk **12907 dan 14365** karena di kedua case eksperimen **menggeser kesimpulan**, bukan sekadar
menambah titik ke kelas jenuh:
- **14365:** sumber menandai case "noise-prone". Klaim itu **tentang alat ukur** → SOP §3d/KH-07
  mewajibkan menjalankannya. Hasil (gold 3/3 PASS, model 3/3 FAIL, deterministik) **membantah**
  noise-prone dan memindahkan vonis dari "mungkin flaky" ke "patch subset, test tajam" (KH-11).
- **12907:** perlu memisahkan "repro salah menilai fix inti" dari "repro buta terhadap kerusakan
  kolateral". Sabotase (gold+`_cdot`-raise → PASS; gold+float → PASS) membuktikan yang kedua.
- **15814:** probe dijalankan untuk **mengukur** over-select (deferred fields gold vs model) —
  mengubah vonis dari dugaan "hijau-dengan-catatan" jadi angka (`['age']` vs `[]`, 3 vs 4 kolom).
- **6938 & 14995:** sabotase TIDAK dijalankan (patch 6938 = gold; kelemahan repro 14995 tekstual
  & F2P resmi sudah menutup fix under-general) — konsisten dengan aturan "hanya bila mengubah
  kesimpulan".
- Jebakan §3d ditangani di keempat probe: interpreter `/opt/miniconda3/envs/testbed/bin/python`,
  `__pycache__` dihapus, `PYTHONDONTWRITEBYTECODE=1`; semua container `probe*` dihentikan+dihapus,
  `git checkout` dijalankan. Nol hasil "terlalu dramatis" (tak ada artefak probe, KH-07).

---

## Catatan penutup autopsi batch bot-04 (2026-07-21) — estafet 22-case, bagian 8 (8 django, bot TERAKHIR)

**Korpus:** 8 case django dijalankan RLFV penuh lewat `scripts/run_rlfv_batch.py`
(`django__django-10924, 11001, 11049, 11133, 11815, 11848, 11999, 12125`), state
`artifacts/batch-bot04.json`. Model `google/gemma-4-31B-it`. Autopsi tiap case oleh satu subagent
read-only (izin eksplisit membantah pemanggil, SOP §6a); integrasi (tulisan ini) serial oleh bot-04.
**Estafet 22-case (7+7+8) SELESAI di batch ini** — bot-04 bot terakhir, tak ada handoff lanjutan.

**11999 dilengkapi bot-04 (bukan lever):** batch runner `qualified_rerun` memungut L qualified
**era-lama** (`l-dev--…--r1/r2/r3`, 2026-07-19, `pass_l1=true` TANPA `candidates.md`) → FIX terblokir
(`localize-tanpa-candidates.md`, gotcha SOP §1c). bot-04 menjalankan **LOCALIZE fresh r4** (qualified +
`candidates.md`) memakai repro qualified r6, lalu FIX r1 — driver standar SOP §1b, bukan penerapan
lever, tanpa rename/hapus run dir.

**Sabotase §3d: NOL dieksekusi di batch ini** (kontras bot-03). Alasan per-case dinyatakan di bawah;
ringkasnya kedelapan vonis tuntas dari artefak statis + F2P/P2P resmi, jadi sabotase hanya akan
mengkonfirmasi ulang fakta yang sudah pasti (aturan §3d: jalankan HANYA bila mengubah kesimpulan).
Semua subagent mencatat prediksi sabotase eksplisit bila kelak dijalankan.

### Papan skor akhir: resolved=5/8 (dari 8 dijalankan); 6 mencapai FIX, 2 berhenti di REPRODUCE

- **Hijau ASLI (patch SEMANTICALLY setara/ekuivalen gold) — 5:**
  - **11049** — **byte-identik gold** (`DurationField` error-string, problem memuat string verbatim).
  - **11001** — setara; operatif = `re.DOTALL` (gold `^`+`re.MULTILINE` **inert** karena `search().group(1)`
    dari pos-0 greedy identik). Repro longgar (except→PASS, K1/K1-ketat/K4/K5) — hijau via kekuatan F2P
    resmi (`assertSequenceEqual`), BUKAN repro.
  - **11133** — setara; cabang `isinstance(value,memoryview): return bytes(value)` ≡ gold widen
    `(bytes,memoryview)`. Repro TERKUAT batch (assert byte-equality, polarity aman) tapi K4 tetap.
  - **11815** — setara (enum serialize by-name; `%r` vs `'%s'` output identik utk nama identifier).
    **r1 gagal ber-label `syntax-fail` PADAHAL `ModuleNotFoundError: repro_app`** (repro in-process
    andalkan modul shell-created; r2 subprocess self-provisioning qualified). Data-point KH-12 lagi.
  - **11848** — setara in-century (bukti aritmetik: `current_year-2000==current_year%100`, boundary
    `>50` identik gold, diverifikasi 7 subtest resmi). **Satu divergensi LEBIH SEMPIT (century hardcode
    `+2000` vs `current_century` dinamis) TAK TERJANGKAU** sampai jam sistem ≥2100 → batas-metodologi,
    LV-14 signature paling remote di korpus.
- **Merah di FIX, akar-MODEL over-broad (patch superset) — 1:**
  - **11999** — `resolved=false`, `file_match=true`, `line_overlap=true`. **F2P `test_overriding_FIELD_display`
    PASS (bug ASLI diperbaiki); 9 P2P regresi** semua `NameError: name 'cls' is not defined`. Gold **1 hunk**
    (`contribute_to_class` guard `if not hasattr(cls,…)`); model **4 hunk** — hunk-1 benar (`cls` in scope),
    hunk 2/3/4 (`get_choices`/`Field.formfield`/`BooleanField.formfield`) menyalin guard ke scope TANPA
    `cls` → NameError. +2 stray empty file (repro-app dir bocor ke diff). Kelas sama **12907 (over-broad
    collateral)**, gejala beda (NameError vs ImportError collection).
- **Merah di REPRODUCE — 2, akar BERBEDA (kedua akar-MODEL, harness bekerja BENAR):**
  - **10924** — repro **won't flip**: base FAIL + patched(gold) FAIL. r1 wrong-predicate (`field.clean(instance)`
    bukan `formfield()`, TypeError arity tak-terkait); r2/r3 predikat benar (`scandir(callable)` TypeError)
    TAPI callable resolve ke dir yang TAK PERNAH ada (`/…/example_dir`, model tak `os.makedirs`) → gold applied
    → FileNotFoundError → FAIL. verdict `wrong-logic`; harness ukur benar, gap = kompetensi model. Keluarga 15789.
  - **12125** — **vacuous repro**: PASS-at-base → anti-vacuous gate menolak (BENAR). Model mereproduksi contoh
    *inner-class-as-field* yang `Field.deconstruct()` sudah perbaiki via `__qualname__`, bukan contoh
    *type-as-value/enum* yang gold `TypeSerializer.serialize` (`__name__`→`__qualname__`) targetkan. Gold
    satisfiable; skenario model bug-free. Budget 40/40 habis, tak pernah pivot KONSTRUKSI (66 [exec], 0
    `<|tool_call|>` — **BUKAN** token-loop 15851).
- **Lulus-palsu tipe file-salah (à la 13658): 0.** Kelima resolved `file_match=true` DAN `line_overlap=true`.
  (Recall detektor rendah — §3b tetap dijalankan; kelima hijau lolos justru lewat §3b analisis semantik.)

### Bukti penguat yang ditambahkan ke entri lever (per case)

- **LV-01 (yardstick/kontrol-positif longgar) — 6 instans baru, K4 di KEENAM repro qualified.** Sumbu paling
  menonjol batch ini. Kelima hijau lolos **karena kekuatan test RESMI, bukan repro** (fix-space sempit +
  model kebetulan menulis fix ≥ tuntutan repro) — sub-pola 11099/13230 "HIJAU tak membuktikan yardstick".
  **11999 = bukti KAUSAL LOAD-BEARING terkuat**: over-broad fix **membalik FIX gate (`flip`) JUSTRU karena**
  repro tak punya kontrol positif yang menyentuh `get_choices`/`formfield`; satu kontrol positif (panggil
  `.get_choices()` pada normal choices field) akan raise NameError → ubah false-flip jadi correct-reject.
  Ini instans pertama di korpus di mana **absennya K4 terbukti kausal atas false-flip yang kemudian
  DITANGKAP P2P resmi** — memisahkan "gap gate internal" dari "validitas vonis" dengan bersih.
- **LV-14 (isi patch-vs-gold tak dibandingkan) — REINFORCED ARAH SUPERSET + koreksi detektor.** 11999: gold
  **1 region**, model **4 hunk** (+2 stray) → over-broad +3, **75% hunk = collateral**. **Koreksi penting ke
  detektor 14365:** detektor murah "mismatch jumlah region hunk + `line_overlap=true` = subset" hanya
  menangkap arah `patch < gold`. 11999 menunjukkan arah `patch > gold` juga berujung `resolved=false` dengan
  `line_overlap=true` — **`line_overlap=true` menyesatkan sbg success-proxy di KEDUA arah** (14365 mask hunk
  HILANG, 11999 mask hunk EKSTRA). **Detektor harus menghitung hunk region gold-vs-patch DUA ARAH** (subset
  DAN superset di file yang sama), bukan hanya subset.
- **LV-09 (`pipe_runtime` tak dikirim ke FIX) — NEGATIVE bersih di KEDELAPAN case.** `grep -c "No module
  named 'pipe_runtime'"` di semua `console.log` fase FIX = **0**; nol repro qualified mengimpor `pipe_runtime`
  (K3 = 0/6). Django murni; K3 tetap tidak menyebar (kini 4/44). (Incidental 10924 r2 repro.py:4 punya
  `from pipe_runtime import App` unused, tapi tak pernah sampai FIX → moot.)

### Reinforcement temuan observability (B) — verdict bucket catch-all, 3 data-point baru

Batch ini menambah **tiga** data-point ke temuan (B) (verdict REPRODUCE menyatukan sebab berbeda), semua
menegaskan aturan **JANGAN percaya label verdict sbg diagnosa**:
- **11815 r1** — `syntax-fail` = `ModuleNotFoundError: repro_app` (repro in-process andalkan modul
  shell-created yg fresh-world tak bawa), **bukan** SyntaxError. Persis pola 15851/KH-12.
- **10924** — verdict `wrong-logic` type-nya benar, TAPI `reason` yang di-append harness
  (`"...likely gold-unsatisfiable predicate"`) **menyesatkan**: r2/r3 predikat SATISFIABLE (cukup `os.makedirs`);
  siapa pun yang percaya `reason` akan salah simpul "gold/case rusak".
- **12125** — verdict None/`pass_l1=false` tak informatif; hanya `events.jsonl` exit `detail.failures`
  ("anti-vacuous PASS-at-base") ungkap akar. **Sub-signature long-runtime BARU:** 20-menit = **budget-exhaust
  productive churn** (66 [exec], reply varied) — INVERSE 15851 (degenerate zero-exec byte-identik). Wall-clock
  sama, mekanisme lawan → **long-runtime saja TAK diagnostik**; wajib cek `[exec]` count + reply variance.

### Kandidat-ditolak (dicatat + syarat naik)

- **"positive-branch precondition not established"** (dari 10924 r2/r3: repro predikat benar tapi callable
  menunjuk dir yg tak di-`makedirs` → gold takkan flip). DISTINCT dari gold-unsatisfiable KH-03 (di sana
  struktural; di sini satisfiable dg 1 baris). **DITOLAK sbg lever** (akar-model, n=1). Syarat naik: ≥3 case
  DISTINCT + fix mekanis (gate pre-create declared dirs / DONE pre-check diff base-vs-head error-class deteksi
  "same exception both worlds").
- **"guard-copied-to-wrong-scope"** (dari 11999 NameError). DITOLAK (gejala model-spesifik, P2P resmi tangkap).
  Syarat naik: collateral lolos P2P resmi juga (silent false-pass) ATAU pola berulang ≥3 case distinct.
- **"L qualified era-lama tanpa candidates.md × `qualified_rerun`"** (observability resume). Selector "last
  qualified L by `pass_l1`" under-specified utk kontrak input FIX (butuh `candidates.md`). **FAILS SAFE**
  (memblokir FIX, bukan memberi input buruk diam-diam) → severity LOW, DITOLAK sbg lever. Syarat naik: bila
  selector kelak menghasilkan FIX SELESAI atas candidate-set degraded (silent bad verdict). Isi konkret bila
  dinaikkan: predikat `qualified` menegaskan kontrak file FIX (`candidates.md` hadir), bukan hanya `pass_l1`.

### Pembaruan Tabel frekuensi (bot-04, 2026-07-21) — 6 case baru ber-repro-qualified

**Denominator.** Sampel Tabel A naik **38 → 44 case** (+6: 11001, 11049, 11133, 11815, 11848, 11999 — masing
punya repro qualified; 11815 di r2, 11999 di r6). **10924 & 12125 TIDAK menambah** (REPRODUCE tak qualified).
`r-dev` delta: +6 qualified + 8 non-qualified (10924 r1-r3 `wrong-logic`, 12125 r1-r3 anti-vacuous, +11815 r1,
+11999 r1-r5 era-lama tak dihitung ulang). Sampel `f-dev` **+6 run** (kelima hijau + 11999).

**Klasifikasi 6 repro baru** (manual, metode sama; per subagent read-only ber-izin-membantah):

- **11001** — K1 Y, **K1-ketat Y** (`except→PASS`), K2 T, K3 T, **K4 Y**, **K5 Y**.
- **11049** — K1 T, K1-ketat T, K2 T, K3 T, **K4 Y**, **K5 Y**.
- **11133** — K1 T, K1-ketat T, **K2 Y** (no try/except, inert), K3 T, **K4 Y**, K5 T.
- **11815** — K1 Y, **K1-ketat Y** (`else→PASS` eksplisit), K2 T, K3 T, **K4 Y**, **K5 Y** (repro r2).
- **11848** — K1 T, K1-ketat T, **K2 Y** (laten, dinetralkan driver-guard), K3 T, **K4 Y**, K5 T.
- **11999** — K1 T, K1-ketat T, **K2 Y**, K3 T, **K4 Y**, K5 T.

**Hitungan K1–K5 diperbarui (denominator 44 case, satu repro qualified per case):**

- **K1: 21 dari 44** (48%). Naik dua: +11001, +11815.
- **K1-ketat: 8 dari 44** (18%). Naik dua: +11001, +11815. Daftar kini 11039, 11910, 12286, 14238, 14580,
  15814, **11001, 11815**. Proporsi tetap minoritas — **KH-05 tetap tidak terbantah**.
- **K2: 15 dari 44**. Naik tiga: +11133, +11848, +11999 (ketiga polaritas aman; K2-nya laten/inert).
- **K3: 4 dari 44**. Tidak berubah (nol dari enam repro baru mengimpor `pipe_runtime`). Kelas tak menyebar,
  konsisten lintas-repo & di seluruh django batch ini.
- **K4: 38 dari 44** (86%). Naik enam (**keenam repro baru K4**). **Tetap kriteria prevalensi tertinggi**,
  makin dominan. Yang punya kontrol positif tetap 6 (10914, 11422 r44, 13768 r4, 14017, 14382 r2, 14580) —
  nol dari batch ini.
- **K5: 27 dari 44** (61%). Naik tiga (+11001, 11049, 11815; 11133/11848/11999 assert kuat → K5 T).
- **Irisan K4 ∧ K5: 23 dari 44** (52%). Naik tiga (11001, 11049, 11815). **Tetap profil kelemahan yardstick
  yang sebenarnya**, > separuh korpus.

**Tabel D (OFF-GOLD) — sweep 6 `f-dev` baru** (semua punya `swebench_eval.json` DAN `gold_eval.json`):
`resolved=true` **5 dari 6** (kelima hijau; 11999 false); **`resolved=true` DAN `file_match=false`: 0** — hit
korpus tetap **hanya 13658**. Denominator `f-dev` ber-kedua-file naik ke **31 run**; `resolved=true` **23 dari
31**; `resolved=true & file_match=false` **tetap 1** (13658), kini **1 dari 23**. **Sel baru: 11999 =
`resolved=false` + `file_match=true` + `line_overlap=TRUE`** — melengkapi 12907 (`resolved=false` +
`file_match=true` + `line_overlap=FALSE`): dua arah kegagalan patch-vs-gold di file yang benar, satu superset
(11999, overlap true) satu rewrite (12907, overlap false). Peringatan recall-rendah tetap penuh — kelima hijau
`file_match=true`+`line_overlap=true` dan **tidak tersentuh** metrik ini.

**Pembacaan yang searah, tidak membalik apa pun.** Enam repro django menegaskan **K4 (kontrol positif absen)
sumbu dominan (38/44, 86%)**, dan 11999 memberi **bukti kausal load-bearing pertama** bahwa absennya K4
membalik gate internal (bukan hanya "berpotensi"). Urutan pemasangan tak berubah: kontrol positif (K4) tetap
kandidat isi konkret pertama LV-01. Tambahan konkret dari batch ini utk LV-14: **hitung mismatch region hunk
DUA ARAH** (subset ∧ superset), karena `line_overlap=true` menyesatkan di keduanya.

---

## Autopsi batch A2 lanjutan (bot-04, 2026-07-21) — 10 case Papan 103 baris 36-45, full R→L→F→V dari nol

**Konteks.** Lanjutan giliran bot-04 (case terakhir board = django-12125, baris 35). 10 case tier A2 (baseline✗ / harness-lama✓ = fix terbukti ada) di-setup fresh dari HF Lite via `scripts/prepare_cases.py`, dijalankan **penuh dari REPRODUCE** (keputusan Mirza: NO bypass R/L). Autopsi via 4 subagent read-only ber-izin-membantah, integrasi serial.

### Papan skor: resolved=8/10; 8 mencapai VERIFY, 2 berhenti di REPRODUCE

- **Hijau-ASLI (3)** — patch setara/verbatim gold:
  - **12497** — patch = gold **verbatim** (hint E334/E335 → ManyToManyField, dua lokasi). Noise: dua file kosong `repro_app/` bocor ke patch (tak berbahaya, kotor).
  - **15790** — patch **byte-identik** gold (`defaultdict(set)` + `sorted(items)`). Hijau paling bersih batch ini.
  - **14787** — setara gold, diverifikasi via kesetaraan mesin `wraps(m)` ≡ `update_wrapper(x,m)` + log 21 test (`__name__` preserved).
- **Hijau-DENGAN-CATATAN (5)** — memperbaiki bug teruji tapi **divergen/longgar** dari gold, lolos karena test/repro tak mengukur divergensi (bukti penguat **LV-14** + **LV-01**):
  - **12708** — rewrite `_delete_composed_index` **membuang guard `exclude=meta_constraint_names|meta_index_names`** → regresi diam-diam pada model ber-`Meta.indexes`/`constraints`. Repro `except Exception → PASS` (katastrofik-mendarat-di-PASS, eksplisit).
  - **14016** — `return self/other` (**aliasing**) vs gold reconstruct-copy; invarian copy pecah, tak terukur (test cek equality bukan identity). Repro terlemah: 1/2 cabang, assert "tak melempar", crash→PASS.
  - **15498** — fix inti ≈setara TAPI rewrite blok import + redefinisi `safe_join` lokal tanpa cek containment → **regresi keamanan path-traversal** (`SuspiciousFileOperation` hilang), tak-terukur test. Repro tanpa assert-nilai.
  - **13447** — core `'model': model` = gold, TAPI **rename tak diminta** `_build_app_dict`→`build_app_dict` (publik) + file kosong `apply_fix.py`. Repro tak menguji jalur view (`app_index`).
  - **12700** — setara fungsional pada jalur teruji; divergensi minor subtipe (`type(value)(...)` vs plain tuple) + key rekursi `None` vs `''`, tak terukur.
- **REPRODUCE-fail (2)** — tak mencapai FIX: **14855, 15902** (lihat sub-signature di bawah).

**Cek lulus-palsu (§3a):** 8/8 resolved `file_match=true` + `line_overlap=true` (diverifikasi per case). **Nol lulus-palsu file-salah.** Peringatan recall-rendah tetap penuh: keempat "hijau-longgar" di atas ber-file_match=true dan **tak tersentuh** metrik eval — divergensi ketangkap HANYA lewat bacaan diff (dasar LV-14).

**K4 (kontrol positif absen):** 7 dari 8 repro qualified. Satu-satunya **K4-PRESENT load-bearing = 13447** (repro mewajibkan DummyModel muncul di `app_list['admin']['models']` dengan metadata benar → build rusak = FAIL; setara contoh 14382 di SOP). Polaritas berbahaya (crash/except → PASS) terlihat eksplisit di **12708, 14016, 12497** (§3c poin c).

### Pembaruan Tabel frekuensi (bot-04, 2026-07-21 batch-2) — 8 case A2 baru ber-repro-qualified

**Denominator.** Tabel A naik **44 → 52 case** (+8: 12497, 12700, 12708, 13447, 14016, 14787, 15498, 15790). **14855 & 15902 TIDAK menambah** (REPRODUCE tak qualified — lihat sub-signature).

- **K4: 45 dari 52** (87%). Naik tujuh (13447 punya kontrol positif → tidak dihitung absen). **Sumbu dominan makin kuat lintas-batch.** Daftar punya-kontrol-positif kini **7** (10914, 11422 r44, 13768 r4, 14017, 14382 r2, 14580, **+13447**).
- **Catatan metodologi:** batch ini prioritas tagging **K4 + polaritas** (poros load-bearing), bukan enumerasi K1–K5 penuh per case — anti-fabrikasi, hanya yang subagent verifikasi eksplisit dicatat. Polaritas `symptom→FAIL / else→PASS` (K1-family) terkonfirmasi minimal di 12708/14016/12497.

**Pembacaan searah, tidak membalik apa pun.** 8 repro A2 menegaskan **K4 sumbu dominan (45/52, 87%)**. Tambahan nyata: **empat "hijau-longgar"** (12708 buang guard, 14016 aliasing, 15498 regresi safe_join, 13447 rename API) = bukti penguat kuat **LV-14** — patch divergen dari gold lolos justru karena file_match=true menutupi perbedaan struktur; hanya bacaan diff yang menangkap.

### Sub-signature REPRODUCE-wall BARU (14855, 15902) — reinforcement temuan (B) + KH-12

**Instansi kedua & ketiga pola KH-12** (verdict `syntax-fail` = mislabel "artefak tak diproduksi"; **0 SyntaxError di 6 rerun**). **Sub-signature BARU, beda dari 15851:**

- **KH-12/15851:** `<|tool_call|>` **tanpa fence** → `has_fences=False`, `format_reminder` **tak menyala**.
- **14855/15902:** fence **ADA** tapi verb tulis-file salah-tag — model emit ` ```python ` alih-alih ` ```file:/path ` (by-design **bukan** aksi-tulis, `gemma_protocol.py`). `format_reminder` **menyala tapi tak efektif** (temp 0.0, model tak berpindah 40 turn ×3). Loop = **"rerun file-hantu"** (`python3 repro.py` atas file yang tak pernah ter-persist), bukan regen byte-identik.
- **Akar-MODEL primer** (instruction-following: prompt + reminder sudah eksplisit menyuruh format `file:`). Akar-HARNESS sekunder (mislabel verdict + tak ada loop-breaker keras).
- **3/6 run tembus produksi file** (via workaround heredoc-bash) → membongkar akar-MODEL laten kedua: repro buggy (phantom app `repro_app` di 14855, halusinasi API `get_admin_url`, **vacuous PASS-di-baseline** di 15902).
- **BUKTI bahwa `format_reminder` saja TAK CUKUP:** reminder sudah menyala di kedua case, tetap gagal — ada **dinding kedua** (logika repro + `repro.md` tak ditulis 0/6). Wall REPRODUCE **berlapis**, akar dominan model.

### Spec improvement (dipertajam, keputusan Mirza 2026-07-21) — verdict label identifikasi-gejala

**Requirement Mirza:** label harus **mengidentifikasi gejala otomatis** (bukan bucket catch-all `syntax-fail`). Mempertajam kandidat #1 temuan (B). Usulan mapping (tiap label derivable dari sinyal yang gate SUDAH punya: `has_fences`, file-persisted?, `REPRO_STATUS` observed, baseline-flip):

- `syntax-error` — repro.py gagal `py_compile` (yang ASLI).
- `repro-missing` — artefak tak pernah ter-persist (protokol/loop). ← 15902 r2/r3, 14855 r3.
- `vacuous-repro` — repro jalan tapi PASS-di-baseline (never-FAIL, tak buktikan bug). ← 15902 r1.
- `gold-wont-flip` / `wrong-logic` — repro FAIL tapi alasan salah / gold tak flip.

**Status: BELUM DITERAPKAN** (default catat-only; menunggu keputusan Mirza apakah di-elevate jadi lever pertama yang diterapkan).

---

## Autopsi batch backlog jalur-1 (bot-04, 2026-07-21) — 9 case lolos-L, FIX+VERIFY (R+L qualified lama)

**Konteks.** 9 case backlog (lolos LOCALIZE, FIX belum tuntas) dijalankan **jalur-1** (keputusan Mirza: terima R+L qualified, FIX+VERIFY saja). Semua both-fail/hard. Autopsi 3 subagent read-only ber-izin-membantah.

### Papan skor: resolved=2/9

- **resolved=True (2):** 11964 (**hijau-ASLI**, `__str__` Choices setara gold), 12747 (**hijau-DENGAN-CATATAN**: fix hanya 1/2 hunk gold — jalur `delete_batch` hilang; lolos karena repro DAN F2P resmi **sama-sama** tak menguji jalur kedua = batas metodologi; +2 file sampah kosong).
- **resolved=False (7):** 7746, 11797, 11910, 13158, 13768, 15320, 15400.

### KOREKSI: "FIX-wall" BUKAN kelas homogen — 3+ kelas, akar berbeda

Mekanisme flip seragam (repro model = yardstick 1-simptom lolos gate, F2P resmi menuntut lebih), TAPI **akar berbeda**. Menamai semua "FIX-wall" salah-arah mayoritas lever:

- **Kelas A — SALAH FILE (akar-LOCALIZE, menyamar FIX-wall): 11797, 13158.** `file_match=FALSE`. File gold **tak pernah masuk kandidat L** (11797: gold `lookups.py`, kandidat `compiler.py`+`query.py`; 13158: gold `sql/query.py`, kandidat `models/query.py`+`compiler.py`). FIX mustahil benar. **Lever = recall LOCALIZE, BUKAN FIX.**
- **Kelas B — repro longgar meloloskan patch meregres (LV-01 murni): 7746.** Patch salah (`len()` vs gold `.size`; 1/2 hunk) meregres 8 P2P, tapi repro tanpa K4 & tak uji input skalar → flip. Di sini ketatkan-repro (K4) VALID.
- **Kelas C — patch destruktif, regresi P2P (akar-MODEL + batas desain gate): 11910.** Model MENGHAPUS blok (arah berlawanan gold yang MENAMBAH). F2P lulus, gagal 1 P2P. **Gate secara desain TAK menjalankan P2P** → regresi P2P mustahil ditangkap gate seketat apapun repro. Perlu ubah kontrak eksekusi gate (jalankan sebagian P2P), bukan prompt/repro.
- **Lain:** 13768 (**F2P brittle exact-string** wording pesan log, unguessable gold-blind — eval valid, batas gold-blind sejati); 15320 (**wrong/narrower mechanism**, tak set invariant `subquery=True`; akar-MODEL); 15400 (**catastrophic hallucination**: rewrite seluruh `functional.py`, hapus `cached_property` → Django tak bisa import → 60+ P2P collapse; **akar-MODEL murni, harness kerja SEMPURNA menangkapnya**).

**Lulus-palsu: 0/9.** Semua 7 resolved=false BENAR. `file_match=false` (11797, 13158) = sinyal akar-LOCALIZE, bukan lulus-palsu.

### Implikasi lever (frekuensi by-AKAR, bukan by-gejala)
Dari 7 fail: **1/7 (7746)** diperbaiki ketatkan-repro (LV-01+K4); **2/7 (11797,13158)** perlu recall LOCALIZE; **1/7 (11910)** perlu gate jalankan P2P; **1/7 (13768)** batas gold-blind (tak bisa diperbaiki tanpa merusak SWE-bench); **2/7 (15320,15400)** akar-MODEL murni (bukan defek harness). **Pelajaran: klasifikasi lever HARUS by-akar; verdict "FIX gagal" cuma gejala.**

### Temuan setup-robustness (tak-bernomor): spec hilang → WAIT diam-diam
3 case backlog (11797, 13158, 15320) `swebench_spec.json` HILANG (setup era lama) → `swebench_checker` exit-1 "spec not found" → `resolved=None` → dashboard nyangkut status **WAIT** (product-pass, menunggu VERIFY) tanpa error keras. Diperbaiki: fetch spec + re-verify (commit `fix(cases)`). **Kandidat improvement:** checker gagal-keras / validasi kelengkapan spec saat setup, bukan diam nyangkut WAIT.

### Addendum: 4 case cand=N (re-LOCALIZE paksa + FIX) — resolved=0/4

4 case (`11422, 12308, 13220, 13401`) L era-lama qualified TAPI tanpa `candidates.md` → di-**paksa re-LOCALIZE** (rerun baru, `scripts/relocalize_candn.py`) sampai candidates.md terbentuk, lalu FIX+VERIFY. Re-localize berhasil (keempat qualified), FIX jalan. Hasil (frekuensi, katalog jenuh):
- **11422** — FIX **no-flip** (pass_l1=false): model tak hasilkan patch yang lolos repro-nya sendiri; `ModuleNotFoundError: pipe_runtime` (LV-09) terpicu di loop kerja FIX. Tak ada `swebench_eval` (tak sampai vonis L2). Kelas: FIX-gagal-produksi-patch.
- **12308, 13220, 13401** — FIX **flip**, `file_match=true`+`line_overlap=true`, **resolved=false** (F2P gagal, p2p_failed ~0). Patch di file benar lolos repro model tapi bukan F2P resmi → **Kelas B (repro longgar / LV-01)**, senada 7746. Menambah instans LV-01: 3.

**Papan skor GABUNGAN 13 backlog: resolved 2/13** (11964 hijau-ASLI, 12747 hijau-catatan). Sebaran akar 11 fail: LOCALIZE-miss 2 (11797,13158) · LV-01/repro-longgar 4 (7746,12308,13220,13401) · destructive+gate-P2P 1 (11910) · FIX-no-flip 1 (11422) · gold-blind-brittle 1 (13768) · wrong-mechanism 1 (15320) · catastrophic-hallucination 1 (15400). **Kontras tajam vs 10 A2 (8/10):** both-fail/hard jauh lebih keras dari tier A2 yang fix-nya terbukti ada.

---

## Reinforcement 2026-07-21 (bot-02) — 14411: instans ke-4 signature KH-12/15851 (no-fence `<|tool_call>`), diamati Mirza saat run grup-1 RLFV

**Konteks.** Grup-1 (41-case belum-tersentuh, estafet bot-04 → bot-02). `django__django-14411` REPRODUCE **tidak qualified 3/3 rerun** (r1/r2/r3), verdict `syntax-fail` = **mislabel** ("required artifacts missing: repro.py, repro.md"), BUKAN SyntaxError. Diamati Mirza langsung di console.log (grep `ReadOnlyPasswordHashWidget` berulang t2–t40).

**Signature = KH-12/15851 variant NO-FENCE (bukan 14855/15902 mis-tag-fence).** Bukti (r1; r2/r3 identik — 39 hit/205 baris tiap run):
- 40 turn semua `[gemma tN] <|tool_call>call:bash` — model pakai protokol tool-call **native-nya sendiri** (`<|tool_call>…<tool_call|>`) **tanpa fenced-block** ```. `parse_actions` → **0 aksi**; **0 baris [exec]/output** di seluruh log → grep **TAK PERNAH** jalan.
- `files/` cuma `pipe_runtime.py` (repro.py tak pernah ter-persist). `done=False, turns=40, attempts=1`.
- Temp 0.0 + konteks tak berubah (aksi tak ter-parse → tak ada observasi baru) → regenerasi **byte-identik** 40 turn. Fixed-point deterministik, bukan "model ngotot grep".
- `has_fences=False` → `format_reminder` **tak menyala** (persis defek 15851; beda dari 14855/15902 yang fence-nya ADA).

**Frekuensi:** signature KH-12 no-fence naik jadi **15851 + 14411 = 2 case × 3 rerun = 6 run**. Keluarga KH-12 mislabel total = {15851, 14855, 15902, 14411}.

**Root (2 lapis, konsisten):** primer **akar-MODEL** (instruction-following — model tak memakai format output harness); sekunder **akar-HARNESS** (verdict mislabel + tak ada pemutus loop no-progress lepas dari `observed_fail`).

**Usulan lever Mirza (2026-07-21): detektor "≥3 command/reply identik berturut → ingatkan/putus loop."** = **persis candidate mechanism #3** temuan observability (B) 15851 ("Pemutus loop no-progress lepas dari `observed_fail`: abort/eskalasi setelah K reply byte-identik"). **DIKONFIRMASI penguat, BUKAN kelas/lever baru** (aturan katalog #3: satu mekanisme = satu lever).
- **Caveat load-bearing:** reminder murni terbukti TAK cukup (14855/15902: `format_reminder` menyala, model tetap gagal 40 turn ×3 di temp-0). Maka breaker efektif harus **mengubah konteks** (mis. suntik parse-failure eksplisit / eskalasi berbeda) ATAU **putus-dini** (hemat 35+ turn terbakar), bukan sekadar menempel pesan yang diabaikan.
- **Prioritas early-cut vs context-change — KEPUTUSAN Mirza (2026-07-21):** **KEDUANYA, berurutan.** Watcher mendeteksi response identik berulang → (1) **putus-dini** loop yang terbakar sia-sia, lalu (2) **inject prompt peringatan mekanis** (workaround ubah-konteks) untuk mencoba pecah fixed-point. Watcher = komponen baru; kedua aksi dipicu dari sinyal "≥K response byte-identik".

**Observasi turunan (bot-02, 2026-07-21) — rerun byte-identik = budget rerun sia-sia di temp 0.0.** `chat()` ketiga driver set `temperature: 0.0` (greedy), tanpa `top_p`/seed (`run_reproduce_gemma.py:110`, `run_localize_gemma.py:71`, `run_fix_gemma.py:110`). Konsekuensi: rerun-sampai-qualified (r1→r2→r3) dgn input identik menghasilkan output **byte-identik** — 14411 r1/r2/r3 semua 39 hit/205 baris. Budget 3-rerun beli **0 informasi** kecuali input berubah antar-rerun. Kandidat lever antar-run (menunggu keputusan Mirza, sumbu reproducibility vs eksplorasi):
- **(a) temperature-di-rerun** (r1 greedy + gate deterministik; r2/r3 temp>0 + **seed dipin** per-rerun → reproducible-given-seed);
- **(b) feedback-injection deterministik** (inject kegagalan rerun sebelumnya sebagai konteks r2/r3 — tetap temp 0.0, tanpa flakiness).
Komplementer dgn watcher (watcher = intra-run; a/b = antar-run).
- **KEPUTUSAN Mirza (2026-07-21):** pilih **(b) feedback-injection deterministik** — utamakan reproducibility bit-for-bit seluruh pipeline; **(a) seeded-temperature DITOLAK** (mengembalikan flakiness pengukuran/vonis). Saat di-elevate nanti: rancang isi feedback yang di-inject ke r2/r3 (kandidat: parse-failure eksplisit / verdict reason rerun sebelumnya / output repro terakhir) — konten feedback = keputusan desain berikutnya.

**Status: BELUM DITERAPKAN** (default catat-only).
