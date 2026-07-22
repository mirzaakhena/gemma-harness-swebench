# Urutan Re-test Lever → Case Asal (strategi validasi lever)

Dibuat 2026-07-22 (bot-04, arahan Mirza via Telegram). Eksekusi dipegang **bot-02**
(estafet board-103-lever-strategy); dokumen ini = urutan + protokol ukurnya.
Basis: [[taksonomi-kegagalan-per-fase]] (kelas & anggota),
[[rekomendasi-lever-dari-taksonomi]] (R1–R19), fingerprint vault
`Papan 103 — Corong Penuh.md`.

> **Terkait:** [[katalog-lever]] (LV-xx) · [[koreksi-hipotesis]] (KH-20 →
> protokol rate §-A0d) · [[sop-rlfv-case-run]] (SOP eksekusi & GPU) ·
> [[rlfv-papan-skor-grup12-dan-retest]] (papan skor & daftar re-test)

**Prinsip Mirza yang dioperasionalkan:** lever lahir dari kasus yang dicatat →
setelah lever dipasang, re-test **case asalnya** (dan case sekelas) untuk melihat
efeknya segera; lever juga bisa lahir dari PASS-yang-tak-efisien.

**Target & tata kerja (Mirza, 2026-07-22):** ekspektasi akhir seluruh gelombang
= **50-60/103 resolved** (pembanding harness-v1 = 45, di rezim yang lebih mudah
dan tanpa dokumentasi selengkap sekarang; posisi kini 40). Tempo **perlahan** —
satu siklus tuntas (pasang → retest → autopsi → keputusan) sebelum gelombang
berikutnya. Pembagian: bot-04 analisa+strategi gelombang (dokumen ini), bot-02
eksekusi lever, bot-03 retest → lapor ke bot-04. **Setelah TIAP laporan retest,
bot-04 wajib analisa ulang — peta gelombang berikutnya BISA BERUBAH** (dokumen
ini living, bukan rencana beku).

## §-A0 — AUTOPSI RETEST BATCH-1 (bot-04, 2026-07-22) — kanari 13230 & temuan metodologi

**Ringkas hasil bot-03 (`artifacts/papan-skor-retest-batch1-g1.md`):** kanari 4/5
selamat (11049, 15790, 15347, astropy-6938 tetap hijau); origin R1 4/4 pipe_err→0
(kelas mekanis LV-09 tertutup) tapi unlock 0/4 (dinding lapis-2); **kanari 13230
JATUH hijau→merah** (baseline r1 rezim-lama resolved, r2 G1 no-flip).

**Autopsi 13230 — VERDIKT: red flag BUKAN regresi lever (false alarm terhadap G1).**
Bukti dari artefak (deterministik, no-GPU):
1. Regresi ada di **fase FIX** (r2 `no-flip`, 16.565 baris console vs r1 602 baris —
   model thrashing rewrite-with-wrong-import `add_domain`, tak pernah hasilkan
   `fix.diff`).
2. **R5-watcher (tersangka bot-03) DIBANTAH:** `no_progress` hanya ter-wire ke
   `run_reproduce_gemma.py`, TIDAK ke `run_fix_gemma.py`; string firing-nya NOL di
   console r2. Watcher tak mungkin jadi sebab regresi fase-FIX.
3. Input frozen **byte-identik** (input-repro.md + input-candidates.md); model,
   driver (`run_fix_gemma-v0`), repro-dir sumber semua sama.
4. **Reply t1 diverge di baris 82 — DI DALAM tulisan file pertama model, SEBELUM
   feedback eksekusi apa pun.** Lever yang menyentuh FIX (R1 ship pipe_runtime; R3
   no-action feedback) HANYA memengaruhi konteks PASCA-aksi; keduanya TIDAK mengubah
   seed/PROTOCOL_NOTE/compose_fix_seed (diverifikasi dari diff `0444b81` & `d592ccc`).
   Karena t1 seed identik tapi output t1 beda → **penyebabnya bukan lever**.
5. Sisa penyebab = **non-komparabilitas rezim inferensi**: r1 dijalankan 2026-07-20,
   r2 2026-07-22 (jeda 2 hari, server vLLM shared). Temp-0 byte-identik hanya
   terbukti DALAM sesi (14411 r1/r2/r3); lintas jeda 2 hari di server yang mungkin
   restart/reload, byte-identitas tak dijamin.

**IMPLIKASI METODOLOGI (update aturan ukur §0):** membandingkan hasil G1 terhadap
baseline hijau LAMA (mingguan) rawan confounder drift-inferensi. **Aturan baru:**
- Kanari & baseline harus **same-session** (jalankan baseline ulang di rezim kini
  sebagai titik banding), bukan hijau historis.
- Vonis unlock/regresi per case butuh **n≥2-3 di rezim yang sama** sebelum
  disimpulkan (bedakan drift-rezim dari efek lever). bot-03 sudah mengusulkan
  re-run 13230 ×2-3 — **didukung**; prediksi bot-04: re-run G1 akan stabil-merah
  antar-satu-sama-lain (drift-rezim), bukan varians acak per-run.
- Angka "40 resolved" & "regression-territory" mengandung noise-rezim — pakai
  sebagai kompas, bukan skor presisi (konsisten §0.5).

**Konsekuensi keputusan:** kanari-jatuh 13230 **TIDAK memblokir G2** (bukan lever
berbahaya). R1 tetap valid (pipe_err→0 = cek mekanis deterministik, kebal
drift-inferensi). Payoff map tak berubah oleh temuan ini; yang berubah = protokol
ukur (same-session baseline + n≥2-3).

### §-A0b — Cek replan R13 (2026-07-22, disetujui Mirza) — HASIL: peta G2 TETAP

Autopsi origin memunculkan 11422 mentok di R13 (App-ready-timeout, kutaruh di G3).
Kucek luas: scan `"failed to become ready"` seluruh console (r/l/f-dev).
- **Terpicu di ~15 case**, TAPI mayoritas **insidental churn**, bukan terminal-wall:
  11910 (akar P2P regresi), 12184 (kompetensi 37×), 11564 & 14752 (akar judge/R17 —
  App-ready hilir orkestrasi paksa), 11620 (resolved=true — churn tak fatal),
  12915/12286/13660 (churn, akar lain).
- **Terminal-wall R13 sejati = 1 case: 11422.** (Origin R1; sudah di
  retest-when-installed queue bot-03.)
- **Baca:** R13 = lever **EFFICIENCY luas** (pangkas turn App-churn di ~15 case) tapi
  **UNLOCK sempit** (≈1 case terminal). Nilai efficiency-nya tinggi, unlock-nya tidak.

**Keputusan replan: R13 TETAP di G3** (disiplin "butuh desain kontrak `run_once` dulu"
tak dilanggar hanya demi 1 case) — tapi ditandai **G3-prioritas-#1** (terminal-wall
11422 + efficiency terluas). **Urutan G2 (R8-R12) TIDAK berubah:** G2 tetap pegang
taruhan unlock terbaik (R8 → 14580, harness murni) + klaster R-4 won't-flip (R9 → 8
case). Contoh replan yang jujur: **cek dilakukan, peta dikonfirmasi tetap** (bukan
tiap data mengubah rencana).

### §-A0c — DISAMBIGUASI EMPIRIS 13230 (bot-03 n=3) — prediksi bot-04 TERBANTAH, temuan STOKASTISITAS FIX

**Prediksiku (§-A0: "re-run G1 stabil-merah byte-identik antar-run = drift-rezim") DIBANTAH
oleh data bot-03.** 13230 di-re-run n=3 di rezim IDENTIK (kini) → **3 trajektori beda
total**: r2 no-flip (patch 14685B), r3 no-flip (attempt-1 kosong 0B), r4 flip-L1 tapi
L2 katastrofik (F2P `test_rss2_feed` fail + 23 P2P regresi); md5 attempt beda antar-sampel.
**Resolve-rate 13230 rezim-kini = 0/3, tapi BUKAN deterministik.** Aku salah menebak
"byte-identik"; bot-03 benar secara empiris.

**Kesimpulan INTI-ku (13230-fall BUKAN regresi lever) TETAP, malah MENGUAT:** variansnya
**intrinsik** (muncul antar-rerun di rezim identik, lever tak menyentuh seed/model). Hijau
historis r1 = satu draw beruntung; merah batch r2 = satu draw sial. Mekanisme = **stokastisitas
FIX**, bukan drift-deterministik (dan bukan lever). *(bot-03 juga mengoreksi diri: "R5 fired
20×"-nya = artefak grep kata `inject`; kami konvergen bahwa R5 tak ter-wire ke FIX.)*

**Rekonsiliasi dengan 14411 (temp-0 byte-identik):** temp-0 greedy ≈reproducible untuk
loop DEGENERAT PENDEK (REPRODUCE 14411 = fixed-point ketat) TAPI **stokastik untuk generasi
PANJANG (FIX)** — di vLLM shared, continuous-batching bikin urutan reduksi floating-point
beda per-request → argmax bisa beda di near-tie; makin panjang generasi, makin banyak titik
divergensi. Jadi asumsi "temp-0 = deterministik" **hanya valid untuk REPRODUCE pendek**.

### §-A0d — PROTOKOL UKUR BERBASIS-RATE (WAJIB sebelum G2; validasi empiris §A0)

Konsekuensi stokastisitas FIX (bukti: 13230 {3 trajektori}, kanari 15790 {hijau↔merah};
**2 dari 5 kanari GOYANG di rezim identik**):

1. **Vonis per-case single-run TIDAK reliable** — termasuk papan skor origin R1 batch-1
   (semua single-run). "0/4 unlock" **bukan bukti case tak-terpecahkan**; 13230 sendiri
   membuktikan loop BISA hasilkan patch (r4 flip-L1) secara stokastik. Angka unlock G2
   single-run akan sama noisy.
2. **Ukur RESOLVE-RATE k/n, bukan biner.** n≥3 minimum (bahkan n=2 kurang — 15790 tak
   sepakat dgn dirinya). Lever "unlock" = **menaikkan resolve-rate** (mis. 0/5 → 3/5),
   bukan satu flip. Kanari "regresi" = **rate turun material**, bukan satu draw merah.
3. **Definisi "solved" (perlu keputusan Mirza):** usul lapor DUA — optimistik
   **pass@n≥1** (resolve ≥1× dari n) dan robust **majority ≥⌈n/2⌉**. Target 50-60/103
   dinilai dengan threshold yang disepakati, bukan single-draw. Baseline "40/103" pun
   single-draw → known-noisy, pakai sebagai kompas.
4. **Kanari sbg detektor-regresi harus rate-based** — kanari single-run tak bisa jadi
   pagar (2/5 goyang). Kanari valid = rate-drop lintas n≥3.

**Implikasi lever (bukan cuma ukur):** (a) trigger R5 "reply byte-identik" TAK akan
menyala di FIX (reply FIX bervariasi — 13230 thrashing dgn reply beda-beda, bukan identik);
port R5 ke FIX butuh trigger LAIN (mis. signature-error berulang / no-diff berulang), bukan
byte-identity. (b) Premis R9 "rerun byte-identik = 0 info" **hanya benar untuk REPRODUCE**;
di FIX rerun sudah bervariasi sendiri.

**Rekomendasi G2:** JANGAN mulai G2 sampai (i) protokol rate disepakati Mirza, (ii)
batch-1 R1 origins di-re-run n≥3 utk resolve-rate riil (0/4 single-run belum final).
Kandidat KH utk bot-03: "temp-0 tak bit-reproducible untuk FIX; FIX stokastik run-to-run".

### §-A0e — KEPUTUSAN Mirza (2026-07-22): PROTOKOL RATE DIADOPSI + gating G2

**Disetujui & DIJALANKAN:**
1. **Protokol resolve-rate** (§-A0d) resmi jadi cara ukur. Vonis FIX = k/n (n≥3),
   bukan biner. Verdict REPRODUCE-wall tetap boleh single-run (andal — 12856 9/9,
   14411 byte-identik; stokastisitas spesifik FIX).
2. **Gating G2:** bot-03 re-run 4 origin R1 (11422, 11910, 15388, 12184) n=3 dulu →
   resolve-rate riil → autopsi bot-04 → BARU brief G2. G2 TIDAK mulai sebelum itu.
   (Dispatched ke bot-03 2026-07-22.)
3. **Definisi "solved" (threshold headline):** BELUM dipatok — lapor rate mentah k/n
   dulu (+ pass@n≥1 optimistik & majority robust), threshold diputus saat lihat angka.
4. **Kanari valid = rate-based** (11049/15347/6938 stabil; 13230/15790 goyang → butuh
   rate). Opsional bot-03 naikkan 13230/15790 ke n=3 utk baseline rate kanari.

Status kerja: G1 terpasang; batch-1 diagnosa selesai (semua single-run → known-noisy);
**menunggu resolve-rate origins (bot-03) sebelum G2.**

---

## §0 — Prinsip pengukuran (WAJIB dibaca sebelum menjalankan urutan)

**§0.0 — Definisi SUKSES per gelombang (disepakati Mirza 2026-07-22).** Ukuran sukses
sebuah gelombang = **berapa DINDING kegagalan yang tertutup**, BUKAN langsung berapa
case FAIL→PASS. Alasan: satu case kerap dijaga BEBERAPA dinding berlapis (contoh:
11422 butuh R1 [✅ G1] DAN R13 [G3] baru bisa PASS). Karena itu **unlock end-to-end
cenderung menggerombol di AKHIR** program, bukan naik linear tiap gelombang. G1 = 0
unlock tapi menutup kelas mekanis (pipe_err, corrupt-gold, false-prune, mislabel) —
itu kemajuan sesuai desain, bukan kegagalan. Target 50-60/103 dinilai di UJUNG, bukan
per-gelombang.

1. **Tiga jenis ekspektasi — jangan diukur dengan metrik yang sama:**
   - **UNLOCK:** harapan FAIL→PASS di case asal. Metrik: verdict L2
     (`swebench_eval.resolved`) + `fix gold_eval.file_match` (aturan §3a).
   - **EFFICIENCY:** PASS tetap PASS (atau FAIL tetap FAIL) tapi lebih murah.
     Metrik: turn terpakai, attempt, wall-clock, jumlah DONE-rejected. Lever jenis
     ini yang dinilai "FAIL→PASS" akan salah divonis gugur.
   - **OBSERVABILITY/INTEGRITAS:** label/atribusi jadi jujur. Metrik: verdict/label
     benar per definisi baru; tidak mengubah resolved sama sekali.
2. **Regression set (kanari) tiap gelombang** — lesson vault (uplift2: unlock 2 case
   sulit, merusak 2 case mudah): setiap gelombang lever diuji pada case asal PLUS
   kanari. **⚠ REVISI 2026-07-22 (§-A0d): kanari harus STABIL-RATE, dan diukur
   rate-based n≥3.** Kanari lama {11049, 15790, 15347, 13230, 6938} ternyata **2 goyang**
   (13230 0/3, 15790 hijau↔merah) di rezim identik → BUKAN pagar valid single-run.
   Kanari-stabil terverifikasi: **11049, 15347, astropy-6938**. Kanari "regresi" =
   resolve-rate turun material, bukan satu draw merah.
3. **Wasit = checker L2**, bukan repro-flip (P23: false-success 20/52 bila L1
   dijadikan wasit). Budget dikontrol saat klaim lift (lesson uplift2-vs-budget).
4. **Label rezim per run:** catat commit harness + lever aktif + injeksi on/off di
   setiap retest. Rerun ber-injeksi (R5/R9) TIDAK comparable dengan rerun temp-0
   polos — pisahkan kolomnya di papan skor.
5. **Acuan fingerprint & kejujurannya:** harness-v1 (uplift6) solve **45/103**
   (single-run pass@1, noisy, belum diverifikasi lulus-palsu); RLFV kini
   **40/103 resolved** (2 di antaranya H-3 divergen: 11620; 13658 lulus-palsu
   terkonfirmasi). Angka dipakai sebagai KOMPAS, bukan skor final.

**Crosstab v1-45 × RLFV-40 (dihitung 2026-07-22 dari fingerprint + sweep artefak):**
- Solved keduanya: **32**. RLFV-baru (v1 ✗ → RLFV ✓): **8** — 12908, 12983 (B0
  regresi-harness-lama), 11964, 12747, 13033, 13315, 13757, 11620†divergen.
- **Regression-territory (v1 ✓ → RLFV ✗): 13 case** — target utama re-test (lihat §4):
  11583, 13590, 14580, 14752, 15789, 15851 (eks-A1) + 12907, 14365, 10924, 11999,
  12125, 14855, 15902 (eks-A2).

---

## §1 — Matrix lever → case asal → ekspektasi → metrik

### Gelombang 1 (9 quick wins Tier-1)

| Lever | Case asal (origin) | Jenis | Yang diukur saat retest |
|---|---|---|---|
| **R1** LV-09 pipe_runtime→FIX (+L) | F-4: `11422, 11910, 15388, 12184` (pipe_err 441/588/232/260) | **UNLOCK** | no-flip hilang? `pipe_err=0`? resolved? (patch tetap tugas model — bisa saja FAIL jujur) |
| (idem, sisi efficiency) | `12286, 13660, 11283, 13448` (terpapar tapi lolos/berjalan) | EFFICIENCY | turn terbuang ke ImportError → 0 |
| **R19** KL-G3-2 prune keying `qualified` | `13964` (re-run manual sudah ada: FIX jalan, resolved=false); 13033 = bukti historis | UNLOCK (terbukti 13033) + INTEGRITAS | tidak ada lagi `skipped-fix-localize-miss` pada `qualified=true` |
| **R18** KL-G3-1 `git apply --check` saat setup | `12856` (repair CONFIRMED bersih 2026-07-22 — tinggal re-run utk status real); historis 12184/13321/14155/15202 | OBSERVABILITY (fail-fast) | setup gagal-keras utk patch korup; nol R-8 baru |
| **R2** split verdict bucket | mislabel keluarga: `15851, 14411, 13265, 14855, 15902, 11815(r1)` + eks-korup | OBSERVABILITY | label baru (`repro-missing`/`vacuous-repro`/`gold-wont-flip`/`gold-flip-crash`) benar per artefak |
| **R3** format_reminder generalisasi (+port F/L) | R-1/R-2: `15851, 14411, 13265, 14855, 15902` | EFFICIENCY → mungkin unlock | reply berubah? repro.py ter-persist? turn hemat |
| **R5** watcher no-progress (putus-dini+inject) | sama dgn R3 + `12125` (trigger #8 observed_fail-never) | EFFICIENCY + mungkin unlock | turn hemat (≥35/run pada fixed-point); fixed-point pecah? |
| **R4** encoding checker | `12907, 14365, 14995` (astropy) | INTEGRITAS eval | `swebench_eval.json` selalu tertulis tanpa PYTHONUTF8 manual |
| **R7** CRLF port ke L | preventif (kelas CRLF historis) | INTEGRITAS | file probe L bebas `\r` |
| **R6** dedup papan batch | pelaporan | INTEGRITAS | denominator ringkasan = case unik |

### Gelombang 2

| Lever | Case asal | Jenis | Yang diukur |
|---|---|---|---|
| **R8** trace hook `.pth` | **`14580`** (L-B; anggota regression-territory!) | **UNLOCK** | LOCALIZE jalan (trace pool terisi) → pipeline lanjut → resolved? |
| **R9** injection antar-rerun (STRICT) | R-4: `15789, 10924, 13933, 15738, 15695, 15252, 15781` + R-5 `12125` | UNLOCK probabilistik | r2/r3 tidak byte-identik; predikat berubah; flip tercapai? (label rezim!) |
| **R10** gate-L baca trace_pool | run tembus-tanpa-DONE (lapisan-2) | INTEGRITAS | tak ada L qualified dgn file ∉ pool |
| **R11** graceful-shutdown | bangkai R-7 (kelas, bukan case) | OBSERVABILITY | run di-kill → verdict `interrupted` |
| **R12** guard timeout FIX + backoff chat | ketahanan | INTEGRITAS | command hang tidak mengabort seluruh run |

### Gelombang 3 (butuh desain dulu)

| Lever | Case asal | Jenis | Yang diukur |
|---|---|---|---|
| **R13** `run_once()` App + kontrak | App-churn: `11039, 11422, 12286, 12915, 13660, astropy-14182` (37×), `14752` | EFFICIENCY | kejadian `unexpected keyword`/ready-timeout ↓; turn ↓ |
| **R14** CONTROL-MARKER (K4 semi-mekanis) | **`11999`** (bukti kausal: kontrol positif akan ubah false-flip→correct-reject) + F-1: `7746, 12308, 13220, 13401` | UNLOCK parsial | model deklarasi kontrol? false-flip berkurang? |
| **R15** detektor hunk dua-arah (eval) | `14365` (subset), `11999` (superset); blind-spot: `12284` | OBSERVABILITY | flag benar di kasus historis; 12284 diketahui TAK tertangkap |
| **R16** pagar edit FIX (himpunan file) | stray-file: `12497, 13447, 11999, 12708, 14730` | INTEGRITAS | nol file sampah/off-candidate di `fix.diff` |
| **R17** reformasi judge (LV-13a) | R-3: **`14752`, `11564`** (dua-duanya wall; 14752 = regression-territory) | **UNLOCK** | checkpoint observed-FAIL tak dibatalkan; wall pecah? |

---

## §2 — Urutan eksekusi yang disarankan (untuk bot-02)

Prinsip urut: (unlock-certainty × jumlah case terbantu) ÷ ongkos; origin dulu, kanari
menyertai; GPU tetap serial + gpu_check (SOP §1a).

1. **Pasang Gelombang 1** (TDD, satu commit per lever) → retest batch-1:
   **origin unlock:** 11422, 11910, 15388, 12184 (R1) + 12856 (pasca-R18/repair).
   **Kanari:** 11049, 15790, 15347, 13230, 6938.
   Catat per §0.4. Ekspektasi jujur: R1 membuka LOOP (bukan menjamin PASS) — model
   tetap harus menulis patch benar.
2. **Retest keluarga token-loop** (pasca R2+R3+R5): 15851, 14411, 13265, 14855,
   15902 — ukur DUA metrik (label benar + turn/unlock). Ini 3 anggota
   regression-territory sekaligus (15851, 14855, 15902).
3. **Pasang R8** → retest **14580** (satu-satunya L-wall; regression-territory).
4. **Pasang R9** (kebijakan STRICT final) → retest R-4: 10924, 15789, 12125 dulu
   (regression-territory), lalu 13933, 15738, 15695, 15252, 15781. Label rezim
   injeksi WAJIB.
5. **Gelombang 3 sesuai keputusan desain Mirza** → R17 retest 14752 + 11564;
   R14 retest 11999 + F-1 (7746, 12308, 13220, 13401); R13 ukur efficiency pada
   App-churn set.
6. Setiap batch retest selesai → autopsi singkat per case (SOP §5) + update
   taksonomi (bot-04) + papan skor rezim-berlabel.

## §3 — Kanari (regression set) — alasan pemilihan

`11049` (byte-identik gold, tercepat), `15790` (byte-identik), `15347` (K4-saja,
predikat nilai), `13230` (setara-semantik, sejarah judge-churn — sensitif ke
perubahan judge/watcher), `astropy-6938` (lintas-repo, jalur encoding). Lima ini
mencakup: fix-space sempit, jalur judge, jalur astropy/encoding. Kanari gagal =
hentikan gelombang, autopsi dulu.

## §4 — Payoff map: 13 regression-territory → kelas → lever penolong

| Case | Kelas taksonomi | Lever yang berpeluang | Realistis unlock? |
|---|---|---|---|
| 14580 | L-B trace | **R8** | TINGGI (harness murni) |
| 14752 | R-3 judge-wall | **R17** (+R13) | SEDANG |
| 15851 | R-1 no-fence | R3+**R5**(+R9) | SEDANG |
| 14855, 15902 | R-2 wrong-tag | R3+**R5**(+R9) | SEDANG (reminder saja terbukti gagal) |
| 10924 | R-4 precondition | **R9** | SEDANG-RENDAH |
| 15789 | R-4 arg-swap | **R9** | SEDANG-RENDAH |
| 12125 | R-5 vacuous | **R9** (redirect skenario) | SEDANG-RENDAH |
| 11999 | F-2 superset | **R14** (kontrol positif) | SEDANG-RENDAH |
| 12907 | F-2 rewrite | (akar-model scope) | RENDAH |
| 14365 | F-3 subset | (akar-model) | RENDAH |
| 13590 | F-3 | (akar-model) | RENDAH |
| 11583 | F-2 rewrite-destruktif (autopsi bot-02 2026-07-22: 297→75 baris, hapus `autoreload_started` → collection collapse) | (akar-model; LV-14 hanya bisa FLAG = observability) | RENDAH |

**Bacaan strategis:** 5-6 dari 13 regresi punya lever harness yang menjanjikan;
sisanya akar-model (gap kompetensi yang v1 "menangkan" lewat rezim lebih mudah —
baseline tak menuntut menulis yardstick sendiri). Payoff map kini LENGKAP — 13/13
terklasifikasi (11583 tuntas 2026-07-22: F-2, realisme RENDAH). Kelas akar-model
kini 5 dari 13 (12907, 14365, 13590, 11999†R14-parsial, 11583).

## §5 — Protokol pencatatan hasil retest (per run)

`case | lever-set aktif (commit harness) | rezim injeksi on/off | verdict per fase |
resolved L2 | fix file_match | turn/attempt | delta vs run pra-lever | catatan`.
Rerun = nomor baru (append-only); papan skor membedakan rezim; lulus-palsu dicek
pakai FIX gold_eval (§3a).

---

*Status (2026-07-22): **Gelombang 1 TERPASANG** (9 lever — R19/R1 bot-04,
R2–R7/R18 bot-02; pytest 465 hijau; hash di header rekomendasi + katalog).
Berikutnya: **retest batch-1 per §2** (origin 11422/11910/15388/12184 + 12856 +
kanari) oleh bot-02, menunggu konfirmasi Mirza. Semua retest berlabel rezim
Gelombang-1 (§0.4). Analisa/autopsi hasil + refresh taksonomi: bot-04.
Gelombang 2/3 tetap catat-only.*
