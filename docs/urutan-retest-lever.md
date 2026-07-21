# Urutan Re-test Lever → Case Asal (strategi validasi lever)

Dibuat 2026-07-22 (bot-04, arahan Mirza via Telegram). Eksekusi dipegang **bot-02**
(estafet board-103-lever-strategy); dokumen ini = urutan + protokol ukurnya.
Basis: `taksonomi-kegagalan-per-fase.md` (kelas & anggota),
`rekomendasi-lever-dari-taksonomi.md` (R1–R19), fingerprint vault
`Papan 103 — Corong Penuh.md`.

**Prinsip Mirza yang dioperasionalkan:** lever lahir dari kasus yang dicatat →
setelah lever dipasang, re-test **case asalnya** (dan case sekelas) untuk melihat
efeknya segera; lever juga bisa lahir dari PASS-yang-tak-efisien.

---

## §0 — Prinsip pengukuran (WAJIB dibaca sebelum menjalankan urutan)

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
   kanari hijau-asli stabil: **11049, 15790, 15347, 13230, astropy-6938** (murah,
   §3b-done, lintas-repo). Kanari berubah status = red flag lever.
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

*Status: menunggu keputusan Mirza kapan Gelombang 1 dipasang. Eksekusi: bot-02.
Analisa/refresh taksonomi pasca-retest: bot-04. Catat-only discipline tetap berlaku
sampai perintah implement.*
