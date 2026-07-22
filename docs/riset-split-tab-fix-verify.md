# Riset: Split Tab "FIX and VERIFY" jadi FIX + VERIFY

Status: riset/analisis effort, BUKAN keputusan final — untuk dipakai Mirza
menimbang sebelum masuk brainstorming/perencanaan implementasi.

> **Terkait:** [[analisis-konsep-split-fix-verify]] (validasi konsep +
> pengecekan sinkronisasi UI ↔ runner, tindak lanjut riset ini)

## 1. Ringkasan eksekutif

Fisibel secara teknis, tapi ini BUKAN pekerjaan kosmetik seperti kelihatannya
dari luar — ide "split tab" menabrak langsung keputusan arsitektur yang sudah
DIKUNCI Mirza sendiri pada 2026-07-20 (spec §6: "TIDAK ada tab keempat",
tercatat eksplisit di kode `ui/server.py:112-115`). Akar masalahnya: tab hari
ini = direktori campaign, sedangkan FIX dan VERIFY yang diminta adalah dua
LAPISAN penilaian (L1 gold-blind vs L2 swebench_checker) atas RUN YANG SAMA
di direktori `f-dev` yang sama — bukan dua populasi run yang berbeda. Maka
solusi yang masuk akal bukan "tab baru = direktori baru", melainkan "virtual
tab" (parameter `view` di atas `f-dev` yang sama), persis seperti yang
disinggung di brief tugas ini. Opsi ini (Opsi A di bawah) saya rekomendasikan:
efort **M, mendekati L** — perkiraan **8–10 task TDD** setara pola repo ini
(lihat `.superpowers/sdd/task-4-brief.md` sebagai contoh granularitas 1
task = 1 fungsi/slice + test), karena harus menjalar ke fungsi status inti
(`case_status`, `stage_summary`), rendering tab (`page_index`), kode fase
clipboard (`campaign_phase`/`copy_case_json`), DAN kontrak API yang BARU SAJA
diterbitkan (`docs/api-ui-viewer.md`). Kabar baiknya: logika "FIX-only" dan
"VERIFY-only" TIDAK perlu ditulis dari nol — keduanya sudah ada sebagai
sub-ekspresi di dalam `_fix_verify_status` (`ui/server.py:393-426`) yang
tinggal diekstrak jadi fungsi murni sendiri, jadi risiko logika baru relatif
kecil dibanding risiko REFAKTOR PLUMBING-nya. Temuan penting yang HARUS
dikonfirmasi ulang oleh Mirza sebelum eksekusi: (a) pembatalan eksplisit
keputusan 2026-07-20 "tanpa tab keempat", dan (b) nama "VERIFY" untuk tab
checker L2 ini akan BERTABRAKAN secara istilah dengan phase `"verify"` yang
SUDAH direservasi di skema kontrak (`harness/emit.py:17`, `docs/kontrak-output.md:53`)
untuk sebuah stage VERIFY produk MASA DEPAN yang belum dibangun (spec §10)
— dua hal yang beda makna tapi nama sama akan membingungkan begitu stage
VERIFY produk itu lahir.

Catatan riset: repo checkout ini TIDAK punya direktori `artifacts/` sama
sekali (bukan hanya `f-dev` kosong) — jadi seluruh analisis di bawah
didasarkan pada kode (`ui/server.py`), kontrak data (`docs/kontrak-output.md`),
kontrak API (`docs/api-ui-viewer.md`), spec desain L2, dan fixture test
(`tests/test_ui_two_layer.py`, `tests/test_ui_api.py`), bukan sampel data
nyata.

## 2. Pemahaman data & kode saat ini

- **Tab = direktori campaign.** `_PIPELINE_STAGES = ("r-dev", "l-dev", "f-dev")`
  (`ui/server.py:116`) dan `_CAMPAIGN_LABELS` (`ui/server.py:108-109`) berpasangan
  1:1 nama-direktori → label. `with_stage_tabs()` (`ui/server.py:149-153`)
  menambah tab pipeline yang direktorinya belum ada (tetap tampil kosong);
  `order_campaigns()` (`ui/server.py:156-160`) mengurutkan sesuai pipeline.
  Tidak ada konsep "view" di lapisan ini sama sekali.
- **`campaign_phase()`** (`ui/server.py:125-136`) memetakan prefix `f-` →
  kode `"FV"` dipakai tombol copy-to-clipboard (`copy_case_json`,
  `ui/server.py:139-146`). Kode "FV" gabungan ini juga perlu dipecah kalau
  FIX dan VERIFY jadi tab terpisah dengan identitas sendiri.
- **Status 2-lapisan `f-*` hari ini** ada di `_fix_verify_status()`
  (`ui/server.py:393-426`), dipanggil dari `case_status()`
  (`ui/server.py:429-480`, khusus baris 453-456 untuk campaign berprefix
  `f-`). Definisi (juga di spec §6, `docs/superpowers/specs/2026-07-20-swebench-checker-l2-design.md:134-139`):
  - `product_pass` = `phases.fix.verdict == "flip"` DAN `pass_l1 is True`
    (baris 401-402) — **inilah "FIX" murni yang diminta**.
  - `resolved = swebench_eval.json["resolved"]` (baris 400) — **inilah
    "VERIFY" murni yang diminta**.
  - PASS = product_pass ∧ resolved=True; FAIL(verify-fail) = product_pass ∧
    resolved=False; **WAIT** = product_pass ∧ swebench_eval.json belum ada;
    **ANOMALY** = ¬product_pass ∧ resolved=True. Keduanya (WAIT, ANOMALY)
    murni sinyal LINTAS-LAPISAN — tidak didefinisikan dalam satu lapisan
    saja.
  - `status_icon()` (`ui/server.py:483-488`) memetakan status → ikon
    (✅❌⏳⚠️), dipakai baris tabel `page_index` (`ui/server.py:1067-1072`) dan
    panel `render_stage_summary` (`ui/server.py:546-592`).
- **`stage_summary()`** (`ui/server.py:491-527`) menghitung "pernah
  qualified" per case dari SEMUA run case itu via `case_status()` — dipakai
  panel ringkasan `page_index` (`ui/server.py:1044-1045`) dan `api_cases`
  (`ui/server.py:746-778`).
- **`page_run()`** (`ui/server.py:1137-1238`) untuk campaign `f-*` (baris
  1164-1214) SUDAH menampilkan KEDUA lapisan sekaligus di satu halaman:
  section "VERIFY (SWE-bench)" (dari `swebench_eval.json`) dan "gold-match
  (advisory)" (dari `gold_eval.json`, terpisah lagi — bukan bagian
  pertanyaan ini). Halaman detail run ini kemungkinan besar TIDAK perlu
  berubah — pemisahan tab adalah soal navigasi/ringkasan, bukan soal
  visibilitas data di detail run.
- **API JSON** (`docs/api-ui-viewer.md`, `ui/server.py:708-778`):
  `/api/campaigns` mengembalikan 3 entri statis (r-dev/l-dev/f-dev,
  `docs/api-ui-viewer.md:31-34`); `/api/runs` dan `/api/cases` menerima
  `c` (nama campaign = nama direktori) dan filter `status` yang divalidasi
  terhadap `_API_STATUSES = ("PASS","FAIL","WAIT","ANOMALY","?")`
  (`ui/server.py:705`, dipakai `ui/server.py:1280-1285`). Tidak ada
  parameter `view` hari ini.
- **Keputusan 2026-07-20 yang tercatat eksplisit** ada DUA tempat:
  komentar kode `ui/server.py:112-115` ("TANPA tab keempat untuk VERIFY
  ... checker L2 adalah pekerjaan VERIFY di dalam tab 'FIX and VERIFY' itu
  sendiri") dan spec `docs/superpowers/specs/2026-07-20-swebench-checker-l2-design.md:124-127`
  ("Tab FIX di-rename 'FIX and VERIFY' ... TIDAK ada tab keempat.
  Struktur/tampilan tab TETAP seperti sebelumnya — hanya label yang
  berubah (keputusan Mirza msg 2297)"). Keputusan ini dikunci lewat
  brainstorm Telegram dengan tombol/pesan eksplisit — bukan default tanpa
  pertimbangan.
- **Kolom "verify" yang SUDAH direservasi di skema, MAKNA BEDA**:
  `harness/emit.py:17` (`PHASES = ("reproduce", "localize", "fix", "verify")`)
  dan `docs/kontrak-output.md:53,67-69` sudah menyediakan phase `"verify"`
  untuk stage VERIFY PRODUK masa depan (bukan checker L2 sekarang — itu
  `pass_l2`/`swebench_eval.json`, realm eval dev, lihat spec §10 baris 186-189:
  "Bentuk stage VERIFY sebagai stage product: diputuskan nanti, di luar
  scope spec ini"). Tidak ada driver `run_verify_*` di `harness/stages/`
  saat ini — stage produk VERIFY memang belum dibangun.

## 3. Opsi desain

### Opsi A — Virtual tab: parameter `view=fix|verify` di atas `f-dev` yang sama (REKOMENDASI)

Direktori `f-dev` TIDAK berubah/tidak dipecah. `page_index` merender DUA
tab link untuk `f-dev` ("FIX" dan "VERIFY"), masing-masing membawa query
`tab=f-dev&view=fix` / `tab=f-dev&view=verify`; tab lama gabungan bisa
tetap ada sebagai `view=combined` (default) untuk backward-compat visual,
atau dihapus dari UI dan disimpan hanya di kode sebagai mode internal.

**Perubahan file/fungsi:**
- `ui/server.py`: ekstrak 2 fungsi murni baru dari isi `_fix_verify_status`
  yang SUDAH ADA — `_fix_only_status(vj)` (pakai ekspresi baris 401-402 apa
  adanya) dan `_verify_only_status(sw)` (pakai ekspresi baris 400) — jadi
  logika bisnisnya BUKAN baru, hanya diberi nama & entry point sendiri.
- `case_status(campaign, run_dir, view="combined")` — parameter baru,
  cabang `f-*` (baris 453-456) memilih salah satu dari 3 fungsi (combined
  lama / fix-only / verify-only) berdasar `view`.
- `stage_summary(campaign_dir, campaign, runs, view="combined")` — teruskan
  `view` ke `case_status` (baris 507, 512).
- `campaign_phase`/`copy_case_json` — perlu varian per-view: `"F"` untuk
  view fix, `"V"` untuk view verify (gabungan `"FV"` tetap untuk
  `view=combined`/default).
- `page_index`: loop tab link (baris 1017-1023) special-case `f-dev` jadi 2
  link; resolusi `active` (baris 1014) jadi pasangan `(campaign_dir, view)`,
  bukan cuma nama campaign; semua pemanggilan `case_status`/`stage_summary`
  di dalam (baris 1044, 1067-1072, dst.) meneruskan `view`.
- `page_run`: kemungkinan TIDAK berubah (tetap tampilkan kedua lapisan) —
  opsional tambahkan breadcrumb "kembali ke tab FIX/VERIFY" berdasar query
  param asal, tapi ini nice-to-have bukan wajib.
- `with_stage_tabs`/`order_campaigns`/`list_campaigns` — TIDAK berubah
  (tetap berbasis direktori); pemisahan murni terjadi di lapisan render
  tab + fungsi status, bukan di penemuan direktori. Ini keuntungan utama
  opsi ini: tidak menyentuh mekanisme discovery campaign yang dipakai
  banyak tempat lain.

**Dampak API & backward-compat:**
- `/api/campaigns`: TAMBAH field `views` opsional pada entri `f-dev`
  (mis. `{"name":"f-dev","label":"FIX and VERIFY","phase":"FV","views":[{"id":"fix","label":"FIX","phase":"F"},{"id":"verify","label":"VERIFY","phase":"V"}]}`)
  — aditif murni, klien lama yang cuma baca `name`/`label`/`phase` tidak
  terpengaruh (kontrak `docs/api-ui-viewer.md:31-34` tetap valid apa
  adanya).
- `/api/runs` & `/api/cases`: TAMBAH parameter opsional `view` (default
  `combined` = perilaku hari ini, identik byte-for-byte dengan sekarang
  bila parameter tak dikirim) — non-breaking. Perlu validasi nilai
  (`fix`/`verify`/`combined`) mirip pola validasi `status` (`ui/server.py:1280-1285`).
- Enum status di dokumen (`docs/api-ui-viewer.md:14-22`) perlu section
  baru menjelaskan makna `PASS`/`FAIL`/`WAIT`/`ANOMALY`/`?` PER VIEW (lihat
  §4 tabel di bawah) — dokumentasi bertambah, bukan berubah breaking.
- **Perkiraan effort: M, mendekati L — ±8-10 task TDD**: (1)
  `_fix_only_status`+test, (2) `_verify_only_status`+test, (3)
  `case_status` threading `view` + regresi test, (4) `stage_summary`
  threading `view` + test, (5) `page_index` render 2 tab link + resolusi
  `(campaign,view)` + test, (6) `campaign_phase`/`copy_case_json` per-view
  + test, (7) `api_campaigns` field `views` + test, (8) `api_runs`/`api_cases`
  param `view` + test, (9) update `docs/api-ui-viewer.md`, (10) opsional
  breadcrumb `page_run`. Risiko utama BUKAN logika (sudah ada), tapi
  PLUMBING: `campaign` sebagai string dipakai luas sebagai kunci dispatch
  (`.startswith("f-")` di banyak tempat) — menambah dimensi `view` di
  sampingnya butuh disiplin supaya tidak lupa satu call site.

### Opsi B — Toggle tampilan di DALAM tab yang sama (label-only / filter klien)

Tetap SATU tab "FIX and VERIFY", tapi tambah kontrol filter (mirip radio
`rowfilter` All/PASS/FAIL yang sudah ada, `ui/server.py:1052-1059`) berlabel
"lensa: gabungan | FIX (L1) saja | VERIFY (L2) saja" yang menyaring/mewarnai
baris di client-side JS memakai `data-status` yang SUDAH dihitung server
(butuh tetap render status per-view ke atribut data baris, jadi tetap perlu
`_fix_only_status`/`_verify_only_status` dari Opsi A, hanya TANPA tab/URL
baru, TANPA parameter API baru).

**Perubahan file/fungsi:** subset Opsi A — item (1),(2) tetap perlu; item
(3)-(4) partial (perlu hitung status per-view untuk ATRIBUT baris, tapi
tidak perlu threading penuh ke `stage_summary`/API); TIDAK menyentuh
`page_index` tab-link loop, TIDAK menyentuh `api_*`, TIDAK menyentuh
`docs/api-ui-viewer.md`.

**Dampak API & backward-compat:** NOL — murni perubahan UI/HTML+JS
lokal, kontrak API tidak tersentuh.

**Trade-off:** Effort lebih kecil (**S–M, ±4-5 task**), risiko lebih
rendah, TAPI **tidak benar-benar memenuhi permintaan "dua tab"** — tidak
bisa di-bookmark/di-share sebagai URL terpisah, tidak muncul sebagai
entitas terpisah di `/api/campaigns` untuk agent lain yang butuh
membedakan FIX vs VERIFY secara programatik. Cocok sebagai MVP murah kalau
kebutuhan sebenarnya cuma "mudahkan mata manusia baca satu lapisan saja",
bukan "agent perlu query FIX terpisah dari VERIFY".

### Opsi C — Campaign/direktori sungguhan terpisah (mis. `f-dev` untuk FIX, `v-dev` baru untuk VERIFY)

Checker L2 menulis hasilnya ke direktori campaign SENDIRI (bukan lagi
`swebench_eval.json` di dalam run dir `f-dev`), mengikuti pola penuh
r-dev/l-dev (punya `verdict.json`, `runs.jsonl`, dst). Ini secara efektif
= **mempromosikan VERIFY dari "eval realm dev" jadi stage produk mandiri**
— yaitu persis hal yang secara eksplisit ditandai DI LUAR SCOPE oleh spec
L2 (`docs/superpowers/specs/2026-07-20-swebench-checker-l2-design.md:186-189`,
§10: "Bentuk stage VERIFY sebagai stage product: diputuskan nanti, di luar
scope spec ini" dan "Tidak ada perubahan schema kontrak-output
(`swebench_eval.json` = file eval realm dev, bukan artefak kontrak)").

**Perubahan file/fungsi:** jauh lebih luas — `eval/swebench_checker.py`
(target tulis), kemungkinan `harness/emit.py` (skema baru), campaign
creation (`harness/make_fix_campaign.py` atau pembuat campaign baru untuk
`v-dev`), backfill/migrasi 13 run f-dev yang sudah ada supaya muncul juga
di `v-dev` (keputusan: run_id sama atau baru?), plus SELURUH perubahan di
Opsi A untuk sisi UI (karena `_PIPELINE_STAGES` sungguh bertambah jadi 4
direktori nyata).

**Dampak API & backward-compat:** `/api/campaigns` akan punya entri BARU
sungguhan (`v-dev`), ini juga aditif, tapi run dir/`verdict.json` untuk
`v-dev` adalah SKEMA BARU yang belum dispesifikasikan — dokumen kontrak
(`docs/kontrak-output.md`) perlu revisi besar, bukan cuma dokumentasi API
viewer.

**Trade-off:** Effort **L, jauh lebih besar (~15-25+ task TDD)** lintas
`harness/`, `eval/`, `ui/`, `docs/` — dan berisiko duplikasi kebenaran
(dua sumber untuk "hasil fix run yang sama"). Hanya masuk akal kalau
tujuan sebenarnya Mirza adalah membangun stage VERIFY produk sungguhan
(yang menurut spec memang arah masa depan tapi SENGAJA ditunda) — bukan
sekadar reorganisasi tab dashboard.

## 4. Definisi status per tab (rekomendasi)

| Kondisi run f-dev | Gabungan (skrg, `_fix_verify_status`) | **Tab FIX (L1 saja)** | **Tab VERIFY (L2 saja)** |
|---|---|---|---|
| flip + pass_l1=True + resolved=True | PASS | **PASS** | **PASS** |
| flip + pass_l1=True + resolved=False | FAIL (verify-fail) | **PASS** | **FAIL** |
| flip + pass_l1=True + swebench_eval.json belum ada | ⏳ WAIT | **PASS** | **⏳ WAIT** ("belum dicek") |
| bukan flip/pass_l1 + resolved=True | ⚠️ ANOMALY | **FAIL** | **PASS** ⚠ *(badge lintas-lapisan, lihat catatan)* |
| bukan flip/pass_l1 + resolved=False/absen | FAIL (product) | **FAIL** | **FAIL** / **`?`** *(bila belum pernah dicek checker)* |
| verdict.json tak ada/rusak | `?` | **`?`** | **`?`** |

Catatan penting:
- **WAIT hanya masuk akal di tab VERIFY** (menunggu checker dijalankan) —
  di tab FIX baris itu memang sudah PASS penuh (L1 tidak peduli L2 sudah
  dicek atau belum), jadi WAIT hilang secara alami dari tab FIX, bukan
  disembunyikan secara paksa.
- **ANOMALY adalah sinyal LINTAS-LAPISAN murni** (disagreement L1 vs L2) —
  tidak punya rumah alami di SATU tab saja. Rekomendasi: JANGAN hapus
  sinyalnya, tapi jangan jadikan status utama di tab manapun. Tampilkan
  sebagai **badge kecil tambahan** ("⚠ kontradiksi L1") di baris tab VERIFY
  yang PASS padahal FIX-nya FAIL (dan sebaliknya opsional di tab FIX) —
  perlu keputusan Mirza: badge di satu tab saja atau dua-duanya (lihat §5).
- Baris "resolved=False/absen" di tab VERIFY untuk case yang L1-nya gagal:
  perlu keputusan Mirza apakah checker MEMANG pernah dijalankan untuk
  case seperti itu (spec tidak mensyaratkan L1 pass dulu — checker cuma
  butuh `fix.diff`) — kalau belum pernah dijalankan, statusnya `?`/WAIT,
  bukan FAIL palsu.

## 5. Risiko & pertanyaan terbuka untuk Mirza

1. **Konfirmasi ulang keputusan 2026-07-20 ("tanpa tab keempat").** Ini
   BUKAN default tak berdasar — dikunci lewat brainstorm Telegram dengan
   rasional eksplisit ("dashboard = alat monitoring development, checker
   ini secara tak langsung pekerjaan VERIFY", spec §6 baris 124-127).
   Permintaan ini secara langsung MEMBALIK keputusan itu. Perlu sign-off
   baru yang eksplisit menyebut bahwa keputusan lama dicabut, supaya jejak
   keputusan (vault/spec) tidak kontradiktif dengan kode.
2. **Tabrakan nama "VERIFY".** Skema kontrak SUDAH mereservasi phase
   `"verify"` (`harness/emit.py:17`) untuk stage PRODUK masa depan yang
   BEDA MAKNA dari checker L2 sekarang (spec §10 eksplisit menunda stage
   itu). Kalau tab dashboard dinamai "VERIFY" untuk checker L2 sekarang,
   lalu suatu hari stage VERIFY produk sungguhan lahir (dengan direktori
   sendiri, `pass_l2` diisi produk, dst) — nama "VERIFY" akan dipakai
   untuk DUA hal berbeda di waktu berbeda. Mirza perlu putuskan: terima
   risiko ini (nama VERIFY dipakai ulang/reinterpretasi nanti), atau pakai
   nama beda untuk tab checker sekarang (mis. "CHECK"/"L2") supaya "VERIFY"
   tetap murni untuk stage produk masa depan.
3. **Apakah `view=combined` (tampilan gabungan hari ini) tetap dipertahankan
   sebagai tab/opsi ketiga, atau dihapus total setelah split?** Kalau
   dihapus, sinyal ANOMALY/WAIT gabungan yang sudah dipakai (asumsi ada
   konsumen/kebiasaan baca sekarang) hilang dari UI kecuali direkonstruksi
   lewat badge lintas-tab (§4).
4. **Perilaku checker terhadap case yang L1-nya belum pernah pass.** Spec
   L2 tidak melarang menjalankan checker pada case yang L1 gagal (checker
   cuma butuh `fix.diff`) — tapi definisi WAIT hari ini (`_fix_verify_status`
   baris 417-420) HANYA berlaku saat `product_pass` true. Kalau tab VERIFY
   berdiri sendiri, perlu keputusan eksplisit soal baris "L1 fail + belum
   pernah di-checker": `?` (belum dinilai) atau ikut ke FAIL.
5. **Badge ANOMALY: satu tab atau dua-duanya?** Serta apakah badge itu
   perlu klik-untuk-detail (pola modal yang sudah ada, `ui/server.py:842-865`)
   atau cukup ikon inline.
6. **Konsumen API eksternal.** `docs/api-ui-viewer.md` baru saja
   diterbitkan (tanggal terkini sekitar 2026-07-2x) — kalau sudah ada
   agent/bot lain yang mengonsumsi `/api/runs?c=f-dev` dan mengandalkan
   makna status GABUNGAN hari ini, menambah `view` sebagai parameter
   OPSIONAL (default tetap combined) aman: tidak breaking. Tapi kalau
   rencananya default justru diganti (mis. default jadi `view=fix`), itu
   BREAKING dan perlu koordinasi/versioning eksplisit dengan konsumen
   tersebut.
7. **Data nyata belum diperiksa.** Repo checkout ini tidak punya
   `artifacts/` sama sekali, jadi belum tervalidasi terhadap run f-dev
   sungguhan berapa banyak yang saat ini WAIT vs ANOMALY vs kombinasi
   lain — sebelum implementasi, ada baiknya cek distribusi nyata (13 case
   populasi f-dev per spec §8) supaya desain badge/tab tidak dibangun buta.

## 6. Rekomendasi

**Opsi A (virtual tab via `view=fix|verify` di atas `f-dev`)** — karena ini
satu-satunya opsi yang (a) benar-benar memberi Mirza "dua tab" seperti yang
diminta, dengan URL/API yang bisa dibookmark dan dikonsumsi agent secara
terpisah; (b) TIDAK menyentuh kontrak data (`docs/kontrak-output.md`) atau
emitter (`harness/emit.py`), jadi risiko regresi ke pipeline harness = nol;
(c) additive terhadap `docs/api-ui-viewer.md` yang baru terbit — tidak
memaksa konsumen lama migrasi; dan (d) logika inti (`product_pass`,
`resolved`) SUDAH ADA di `_fix_verify_status`, tinggal diekstrak — effort
riil didominasi PLUMBING (threading parameter `view` ke ±6-7 fungsi/pemanggil)
yang mekanis dan mudah diverifikasi test, bukan desain algoritma baru.
Opsi B masuk akal HANYA sebagai langkah antara murah kalau Mirza mau coba
dulu tanpa komit ke perubahan API. Opsi C ditolak untuk permintaan ini —
itu proyek berbeda (mempromosikan VERIFY jadi stage produk), sudah sengaja
ditunda di spec §10, dan tidak sepadan dengan "split tab dashboard".

Sebelum implementasi jalan, DUA hal di §5 (poin 1 dan 2) sebaiknya
diklarifikasi eksplisit dengan Mirza dulu — keduanya murah untuk ditanyakan
sekarang, mahal untuk diperbaiki setelah kode & dokumen kontrak ditulis
ulang.
