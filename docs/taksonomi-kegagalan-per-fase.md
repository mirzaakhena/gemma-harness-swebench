# Taksonomi Kegagalan Per-Fase — pipeline RLFV (REPRODUCE / LOCALIZE / FIX / VERIFY)

Dibuat 2026-07-21 (bot-04, Fable 5; handoff parsial dari bot-03,
`.handoff/202607211516-prompt-taksonomi-kegagalan-per-fase.md`). Plane: SMARTXRESE-391
(induk retest 103) / SMARTXRESE-397 (task dokumen ini).

**Apa dokumen ini:** SATU peta kegagalan pipeline, dipecah per fase, yang menyatukan
taksonomi parsial yang selama ini tersebar (Kelas A/B/C di ekor `katalog-lever.md`,
sub-signature REPRODUCE-wall di `koreksi-hipotesis.md` KH-10/12/15, papan skor
`rlfv-papan-skor-grup12-dan-retest.md`). Tiap kelas memuat: **signature/cara deteksi
operasional** (artefak + field), **akar** (model / harness / metodologi — by-AKAR, bukan
by-gejala), **lever terpetakan** (tunjuk LV-xx, tidak menulis ulang isinya), **frekuensi
absolut + denominator + apa yang benar-benar diperiksa**, dan **daftar case anggota**.

**Apa yang BUKAN dokumen ini:** strategi pemasangan lever dan urutan re-test — itu milik
Mirza (keputusan brainstorming handoff). Dokumen ini bahan mentahnya.

---

## 0. Metode, denominator, dan disiplin baca

**Sweep mekanis 2026-07-21 (bot-04) — SELURUH artefak diperiksa otomatis, bukan sampel:**

- `artifacts/r-dev` = **220 run, 84 case**; `artifacts/l-dev` = **135 run, 67 case**;
  `artifacts/f-dev` = **66 run, 63 case** (termasuk `14534` grup-3 yang masih in-flight
  saat sweep).
- Field yang dibaca per run: `verdict.json` → `phases.<stage>.verdict`, `pass_l1`,
  `wall`; `gold_eval.json` → `file_match`, `line_overlap`; `swebench_eval.json` →
  `resolved`, `f2p_failed`, `p2p_failed`; keberadaan `files/repro.py`, `files/repro.md`,
  `files/candidates.md`; hitungan substring `console.log`: `[exec]`, `<|tool_call`,
  `unexpected keyword argument`, `No module named 'pipe_runtime'`.
- **Klasifikasi AKAR hanya diberikan pada case yang sudah diautopsi** (katalog-lever /
  koreksi-hipotesis / papan skor). Case yang baru tersentuh sinyal mekanis tapi belum
  dibedah diberi tanda **⏳ belum-diautopsi** — jangan dikutip sebagai akar.
- **Korpus MASIH BERTAMBAH**: bot-03 sedang menjalankan grup-3 (10 case) lalu grup-4
  (11 case). Saat sweep, baru `14155` selesai (REPRODUCE-wall 3×`wrong-logic`) dan
  `14534` in-flight. **Refresh dokumen ini setelah grup-3/4 mendarat** (lihat §7).
- **Bias yang wajib dibaca bersama angka per-run:** kampanye rerun menumpuk di sedikit
  case — `11422` = 44 run r-dev; `11797` = 15 run l-dev; `11964` = 15 run l-dev
  (kampanye eksperimen era L#1–L#3). Angka per-case lebih jujur daripada per-run.
- **Jangan percaya label verdict sebagai diagnosa** (bias ke-3, KH-11/KH-12/KH-15).
  Label `syntax-fail`/`wrong-logic` di bawah selalu diberi tanda kutip karena keduanya
  bucket catch-all (lihat R-1/R-2 dan temuan observability (B) di katalog).

**Funnel per-case (mekanis — REFRESH 2026-07-22, pasca grup-3/4 + repair gold KH-16;
board 103 kini tersentuh penuh):** **103 case** masuk REPRODUCE (261 run) → **83** punya
≥1 repro qualified (**20 wall di R**) → **82** lolos LOCALIZE (**1 wall di L**: 14580) →
**75 case** punya run f-dev (sisanya: prune localize-miss + 13925 dihapus + 11797 f-dev
dihapus, §6.5) → **40 run resolved=true** (38 `file_match=true` + 2 `file_match=false`),
**26 run resolved=false**, **5 no-flip tanpa eval** (per-run; 11910 & 13660 run ganda).
Verdict r-dev per-run: `pass` 127 · `wrong-logic` 88 · `syntax-fail` 27 · `fail` 10 ·
tanpa-verdict 9. (Funnel 2026-07-21 pra-grup-3/4 tersimpan di git history dokumen ini.)

---

## §R — Fase REPRODUCE

REPRODUCE-wall = mode kegagalan **dominan** (sweep 2026-07-22: 20 dari 103 case tak
pernah qualified). Wall R menghentikan seluruh pipeline — case-case ini tak menyumbang
data L/F/V sama sekali.

**Denominator R (refresh 2026-07-22):** 261 run / 103 case, semuanya tersapu mekanis.

**20 case tak pernah qualified:** 10924, 11564, 11630, 11905, 12125, 12856, 13265,
13933, 14411, 14608, 14667, 14752, 14855, 15252, 15695, 15738, 15781, 15789, 15851,
15902. **Catatan KH-16:** 12184/13321/14155 KELUAR dari daftar wall — gold.patch-nya
korup (R-8); pasca-repair ketiganya qualified R dan lanjut ke L/F. 12856 masih wall
(6 run `wrong-logic`; status pasca-repair perlu konfirmasi bot-03).

### R-1 — Token-loop tanpa fence: repro TAK PERNAH ditulis (keluarga KH-12 "no-fence")

- **Signature (operasional):** `files/` hanya berisi `pipe_runtime.py` (TIDAK ada
  `repro.py`); `console.log` dipenuhi `<|tool_call>` (≈40/run) dengan 0 atau sangat
  sedikit baris `[exec]`; reply (nyaris) byte-identik antar-turn (temp 0.0); verdict
  `syntax-fail` ("required artifacts missing") — **mislabel**, bukan SyntaxError.
- **Akar:** **MODEL primer** (instruction-following: memakai protokol tool-call
  native-nya sendiri, bukan format fence harness) + **HARNESS sekunder** (mislabel
  verdict; `format_reminder` hanya menyala bila `has_fences=True`; tak ada pemutus loop
  no-progress lepas dari `observed_fail`).
- **Lever:** temuan observability **(B)** kandidat #1 (split verdict bucket — spec label
  identifikasi-gejala Mirza: `repro-missing`), #2 (generalisasi `format_reminder`),
  #3 (**watcher no-progress**: putus-dini + inject — keputusan Mirza 2026-07-21,
  tercatat di reinforcement 14411). Bukan LV bernomor.
- **Frekuensi:** **3 case × 3 rerun = 9 run** (semua diperiksa): `15851`, `14411`,
  **`13265` (temuan sweep ini — anggota kelima keluarga KH-12, lihat §6.3)**. Plus 1 run
  non-wall: `11797` r1 (60 `<|tool_call`, pulih di r2+).
- **Anggota (wall):** 15851, 14411, 13265.

### R-2 — Fence ada tapi salah-tag: file tak pernah ter-persist ("rerun file-hantu")

- **Signature:** `console.log` punya fence tapi verb tulis-file memakai ` ```python `
  alih-alih ` ```file:` → `parse_actions` tidak menganggapnya aksi-tulis;
  `format_reminder` MENYALA tapi tak efektif 40 turn ×3; sebagian run tembus menulis
  via heredoc-bash tapi repro-nya buggy; `repro.md` tak pernah ditulis (0/6);
  verdict `syntax-fail` (mislabel yang sama dengan R-1).
- **Akar:** **MODEL primer** (instruction-following — reminder sudah terkirim, tetap
  gagal ⇒ reminder murni terbukti TIDAK cukup), **HARNESS sekunder** (mislabel +
  tanpa loop-breaker).
- **Lever:** sama dengan R-1 ((B) #1/#3; watcher). Catatan penting untuk strategi:
  R-2 adalah bukti bahwa lever "perbaiki reminder" saja tidak menyelamatkan.
- **Frekuensi:** **2 case × 3 rerun = 6 run** (semua diperiksa): `14855`, `15902`.
- **Anggota:** 14855, 15902.

### R-3 — Judge memaksa buang checkpoint known-good → orkestrasi yang mati (LV-05 → LV-12)

- **Signature:** `console.log` memuat checkpoint in-process yang observed-FAIL
  (`repro-first-fail.py` di `files/`) → baris `[judge]` menolak (kutipan khas:
  "real WSGI server" / "follow the user's action path" / `rule:app-runtime`) → model
  pivot ke orkestrasi (runserver/HTTP/login/subprocess) → mati di titik gagal yang tak
  berhubungan dengan bug (SyntaxError peluncur `python3 -c` di 11564; CSRF-403 di
  14752); `flip_run.json` base=FAIL & patched=FAIL; verdict `wrong-logic` dengan reason
  "gold-unsatisfiable" yang **menyesatkan** (gold satisfiable).
- **Akar:** **HARNESS primer (LV-05)** — judge menahan bukti yang sudah disaksikan;
  **LV-12** (orkestrasi menyeret titik gagal); **akar-MODEL sekunder** (eksekusi pivot
  yang rapuh). Flip-gate sendiri BEKERJA BENAR (nol hijau-palsu).
- **Lever:** **LV-05** (argumen sah: ongkos-turn + risiko-ekor, BUKAN laju gagal —
  KH-04), **LV-13(a)** (kewajiban bukti > filter kategori; LV-05(b) mekanika-saja
  terbukti tak menyelamatkan), **LV-08** (reinstatement checkpoint), **LV-12**.
- **Frekuensi wall:** **2 case** gagal total karena rantai ini: `14752` (3 run,
  ≈84 menit, terpanjang di korpus R), `11564` (r3; r1 juga `wrong-logic`, r2 bangkai).
  Ongkos-turn non-wall (ditahan judge lalu tetap qualified, bentuk beku memburuk):
  12915, 13230, 12286, 11039, 14382 (terdokumentasi di LV-05/LV-01).
- **Anggota (wall):** 14752, 11564. (Kena-ongkos non-wall: 12915, 13230, 12286, 11039, 14382.)

### R-4 — Wrong-predicate / won't-flip (bucket `wrong-logic`, akar-MODEL)

- **Signature:** repro DITULIS dan JALAN; `flip_run.json` base=FAIL patched=FAIL
  (gold tak mem-flip) ATAU predikat menguji skenario yang salah; verdict `wrong-logic`.
  **Wajib buka `flip_run.json` + `console.log`** untuk memisahkan sub-sebab — reason
  yang di-append harness ("likely gold-unsatisfiable predicate") beberapa kali terbukti
  menyesatkan (10924, 11564, 14752).
- **Sub-sebab terkonfirmasi:** salah pemetaan argumen API (`15789`); precondition tak
  ditegakkan (`10924`); predikat gold-unsatisfiable sungguhan (`11039` r1); setup tak
  lengkap (`14382` r1); scaffolding subprocess SyntaxError (`11564` r3 — overlap R-3);
  **+grup-3/4 (autopsi bot-03):** repro menguji SITE yang salah (`15252` recorder vs
  executor; `13933` validate() vs to_python); salah paham semantik fix (`15781`
  newline-preservation yang gold tak janjikan); repro BYPASS jalur yang gold perbaiki
  (`15738` hand-author migration, autodetector tak terpanggil); scaffolding mock
  salah-tipe crash dua-dunia (`15695` Options vs ModelState).
- **Akar:** **MODEL** (kompetensi konstruksi repro); harness/flip-gate mengukur benar.
  **PRASYARAT klasifikasi (pelajaran KH-16): cek dulu `git apply --check gold.patch`
  bersih — `wrong-logic` bisa lahir dari gold korup (R-8), bukan model.**
- **Lever:** tidak ada lever tunggal — kandidat-ditolak tercatat (positive-branch
  precondition; PASS_OBSERVABLE friction). Yang sah: split reason bucket via
  `flip_run.json` ((B) #1) — kini termasuk memisahkan sub-sebab `corrupt-gold`.
- **Frekuensi (refresh 2026-07-22):** verdict `wrong-logic` = **88 run** (semua
  tersapu). Terkonfirmasi akar-MODEL: **7 case** — 15789, 10924, 15252, 15781, 13933,
  15738, 15695 (+11564 di R-3). **KH-16: 12184/13321/14155 DIKELUARKAN dari
  kandidat R-4** (akar-DATA, kini R-8). **⏳ belum-diautopsi tersisa: 11630, 11905
  (6 run), 14608, 14667, 12856 (gold pasca-repair perlu konfirmasi).**
- **Anggota (terkonfirmasi):** 15789, 10924, 15252, 15781, 13933, 15738, 15695.
  (⏳: 11630, 11905, 14608, 14667, 12856.)

### R-5 — Vacuous / PASS-at-base: gate anti-vacuous menolak (gate BEKERJA BENAR)

- **Signature:** verdict `fail`; `events.jsonl` exit `detail.failures` memuat
  anti-vacuous "PASS at base"; `[exec]` banyak dan reply bervariasi (churn produktif)
  tapi budget habis. **INVERSE R-1**: wall-clock panjang yang sama, mekanisme
  berlawanan — long-runtime saja TIDAK diagnostik; cek `[exec]` count + variance reply.
- **Akar:** **MODEL** (mereproduksi skenario yang bukan bug-nya — 12125 mereproduksi
  kasus yang sudah diperbaiki `__qualname__`, bukan target gold).
- **Lever:** tidak ada (gate bekerja sesuai desain). "Repro mencetak PASS di base
  sehingga DONE ditolak" = 89 kejadian/15 run/9 case di aliran retry (Tabel B) —
  volume itu BUKAN cacat.
- **Frekuensi wall:** **1 case** (`12125`, 3×`fail`). 15902 r1 juga vacuous-PASS-at-base
  tapi akar dominannya R-2.
- **Anggota:** 12125.

### R-6 — Churn API `App` / halusinasi signature (bukan wall sendiri, pembakar turn)

- **Signature:** `console.log` berisi `__init__() got an unexpected keyword argument
  'text'/'capture_output'/'env'` → konstruktor `pipe_runtime.App` (halusinasi signature
  App — **KH-15**); bedakan dari `run() got …` = genuine `subprocess.run` Python 3.6
  (**KH-10**). Kelompokkan berdasarkan SEBAB, bukan teks error.
- **Akar:** **MODEL** (halusinasi API) di atas **HARNESS** (API App yang tak ramah
  one-shot — LV-06).
- **Lever:** **LV-06** (`App.run_once()` + output terbaca program) — kelas bernama
  terbesar di korpus (33 kejadian/21 run/8 case per Tabel B; +14752 5× "failed to
  become ready").
- **Frekuensi:** sweep kolom `unexpected keyword argument`: kejadian tersebar luas;
  terbesar `astropy-14182` r1 = **37 kejadian** (case ini tetap qualified — churn ≠
  wall). Angka basis Tabel B jangan ditimpa (matcher asli belum direkonstruksi —
  peringatan bot-01 tetap berlaku).

### R-7 — Bangkai interupsi (tanpa `verdict.json`) — bukan kegagalan model

- **Signature:** run dir tanpa `verdict.json` sama sekali (sweep: **9 run** dari 220);
  dashboard lama menandai "(live)" selamanya.
- **Akar:** **HARNESS-robustness** (tak ada penulisan verdict saat kill/interrupt).
- **Lever:** kandidat **graceful-shutdown** (verdict `interrupted`, katalog bot-02).
- **Anggota (teridentifikasi interupsi):** 11019 r1, 15819 r1, 11620 r2, 11564 r2;
  sisanya run era-lama (11422 r1/r7/r19/r28, 12453 r1, 13925 r1). Semua case-nya
  qualified di rerun berikutnya kecuali 11564/13925.

### R-8 — Gold.patch KORUP → flip vacuous, mislabel `wrong-logic` (akar-DATA/setup; KH-16) — BARU 2026-07-22

- **Signature (operasional):** `flip_run.json` = `{"output":"error: corrupt patch at
  line N","exit":128}` — `git apply` gagal di level PARSE, `&&` short-circuit, repro
  TAK PERNAH jalan di gold-world; `gate_runs.json` base menunjukkan repro JALAN dan
  `REPRO_STATUS: FAIL` benar. Deteksi independen tanpa run: `git apply --check
  cases/gold/<id>/gold.patch` → "corrupt patch". Verdict `wrong-logic` = MISLABEL.
- **Akar:** **HARNESS/DATA-setup** — bug `prepare_cases` (`patch.rstrip()` menghapus
  baris konteks trailing → body hunk < header). **BUKAN model, BUKAN repro.** Flip
  gate sendiri aman (nol hijau-palsu); yang tercemar = atribusi kegagalan. Sudah
  di-fix commit `471cb6d`.
- **Lever:** **KL-G3-1** (validasi `git apply --check` saat setup, gagal-keras) —
  katalog ekor grup-3.
- **Frekuensi:** **5/97 gold.patch django korup** (scan penuh `git apply --numstat`):
  12184, 12856, 13321, 14155, 15202. Pasca-repair: 15202 tervalidasi flip PASS
  (adjudikasi adil, kini F-3); 12184/13321/14155 qualified R dan lanjut (12184 → F-4
  no-flip; 13321/14155 → merah VERIFY target-fail, belum diautopsi); 12856 masih wall.
- **Anggota (historis):** 12184, 12856, 13321, 14155, 15202. **Pelajaran taksonomi:
  3 di antaranya sempat salah kutaruh sebagai kandidat ⏳ R-4 akar-MODEL — koreksi
  KH-16 (bias-3 varian data-korup).**

---

## §L — Fase LOCALIZE

**Denominator L:** 135 run / 67 case, semua tersapu mekanis.

### L-A — Kelas-A: recall-miss — file gold tak pernah masuk kandidat (`file_match=false`)

- **Signature (operasional):** `l-dev` `gold_eval.json` → `file_match=false` pada run
  qualified **yang dipakai FIX** (bukan sembarang run; lihat catatan 11964 di bawah).
  `line_overlap` di kasus ini `null` — **BUKAN false** (KH-13/KH-14: tak terhitung
  karena filenya beda; detektor wajib memperlakukan `null` sebagai sel tersendiri).
  Konfirmasi: `localize.md`/`candidates.md` nol menyebut file/simbol gold.
- **Akar:** **LOCALIZE-recall** (bukan FIX, bukan repro). Kelas ini sering MENYAMAR
  sebagai FIX-wall di papan skor lama (koreksi "FIX-wall bukan kelas homogen").
- **Lever:** kandidat bot-02 **keputusan Mirza (1)+(2)**: (1) `--prune-localize-miss`
  (orkestrasi, SUDAH terpasang `de43a91` — 12113 terbukti ter-skip benar) + (2) gate
  LOCALIZE blind cross-check kandidat-vs-file-yang-disentuh-repro (KANDIDAT, belum
  diterapkan). DILARANG cek-gold di gate produk (gold-blind).
- **⚠ DEFINISI DIPERTAJAM (KH-17, 2026-07-22):** Kelas-A sejati = **`qualified=false`**
  (gold tak ada DI MANA PUN di shortlist — recall benar-benar gagal). Signature
  `file_match=false ∧ qualified=true` (pointed primer salah TAPI gold ada di
  candidate lain) **BUKAN Kelas-A** — itu recall SUKSES; kalau di-skip prune, itu
  **false-prune** (bug keying `should_prune_fix`, lever KL-G3-2 — terbukti
  mengorbankan solve nyata: 13033 recovered jadi resolved=true saat re-run tanpa
  prune). Kontaminasi terdeteksi: `11742` ternyata `qualified=true` → KELUAR dari
  Kelas-A sejati (kegagalannya di FIX, bukan recall).
- **Frekuensi (refresh 2026-07-22):** Kelas-A sejati ber-`qualified=false`
  terkonfirmasi **6 case**: `13158`, `12113`, `15213`, `12589`, `14997`, `14999`.
  Belum-dicek sumbu `qualified`-nya: `11797`, `13925` (era sebelum field ini
  diperhatikan). Sweep per-run `file_match=false` pada L-qualified-terakhir = 14 case
  — campuran Kelas-A sejati + false-prune-signature + nuansa di bawah:
  - `11620` — file_match=false di L DAN F, tapi **resolved=TRUE** (F2P + 66 P2P lolos,
    0 regresi). Kandidat "fix-alternatif-lokasi-valid" — butuh §3b sabotase (papan §3).
    Kelas-A tidak selalu berakhir merah.
  - `11964` — r2–r15 (kampanye eksperimen era-lama) file_match=false, tapi **FIX
    memakai r1 yang file_match=true** → hijau-asli. **BUKAN Kelas-A end-to-end.**
    Pelajaran metodologi: heuristik "run qualified terakhir" menyesatkan pada case
    ber-kampanye; yang menentukan adalah run yang benar-benar jadi input FIX.
- **Sub-split gold-unguessable vs kelalaian:** dinilai eksplisit **2 case**:
  `12113` (traceback generic-layer, gold di `sqlite3/creation.py` yang tak tersebut)
  dan `15213` (model paham mekanisme benar di `WhereNode.as_sql`, gold fix di hook
  `BooleanField.select_format` yang tak terduga). `12589` dinilai **near-miss**
  (mekanisme teridentifikasi, meleset file sejengkal). Sisanya belum dinilai —
  jangan diekstrapolasi; murah dinilai (problem statement vs file gold).
- **Anggota (Kelas-A sejati):** 13158, 12113, 15213, 12589, 14997, 14999
  (+belum-dicek-qualified: 11797, 13925; +nuansa: 11620, 11964; KELUAR: 11742).

### L-B — Trace-pool kosong: repro subprocess mematikan LOCALIZE sebelum LLM (akar-HARNESS)

- **Signature:** `verdict.json` L `pass_l1=false` verdict `syntax-fail` dengan failures
  "artefak wajib tidak ada: localize.md"; `files/` **kosong total**; `events.jsonl`
  event `abort` "trace pool is empty"; deterministik 3/3 (retry mustahil menolong).
  Prasyarat: repro input berbentuk `subprocess.run([sys.executable, ...])`.
- **Akar — DIPERSEMPIT (verifikasi kode bot-04, 2026-07-21):** tetap **HARNESS**,
  tapi BUKAN "trace tidak mengikuti fork" — follow-child SUDAH diimplementasikan
  (`localize_trace.py:98-107` + `trace_sitecustomize.py`, hook via `PYTHONPATH`).
  Akar sebenarnya: repro 14580 **menimpa PYTHONPATH** di env child
  (`env["PYTHONPATH"] = str(testbed)` di `r-dev--…-14580--r1/files/repro.py`) →
  sitecustomize tak termuat di child; induk tak mengeksekusi file repo in-process →
  pool kosong → abort. Model TAK PERNAH dipanggil; retry 3× mustahil menolong.
- **Lever:** pindahkan hook ke site-packages container via file `.pth` (kebal
  penimpaan PYTHONPATH) — lihat `rekomendasi-lever-dari-taksonomi.md` R8. Alternatif
  "gate R melarang repro subprocess" TIDAK disarankan (pola sah).
- **Frekuensi:** **1 case × 3 run = 3/3** (`14580`) — satu-satunya L-wall di korpus.
- **Anggota:** 14580.

### L-C — L qualified era-lama tanpa `candidates.md`: FIX terblokir (fails-safe)

- **Signature:** `l-dev` `pass_l1=true` TAPI `files/candidates.md` tidak ada → FIX
  menolak input. Sweep: **25 run / 7 case** (11422, 11797, 11964, 11999, 12308, 13220,
  13401 — semua era-lama; era baru selalu menulis candidates.md).
- **Akar:** **HARNESS-observability** (selector `qualified_rerun` under-specified) —
  FAILS SAFE (memblokir, bukan memberi input buruk diam-diam).
- **Lever:** kandidat-ditolak (severity LOW); penanganan operasional sudah terbukti:
  re-LOCALIZE fresh (11999 r4; `relocalize_candn.py` untuk 11422/12308/13220/13401).
- **Anggota:** 11999(r1–r3), 11422, 12308, 13220, 13401, 11797, 11964 (run era-lama).

---

## §F — Fase FIX

**Denominator F:** 66 run / 63 case tersapu mekanis; 62 case tuntas eval saat sweep.
Sel mekanis (per-run): resolved=true+fm=true **35** · resolved=true+fm=false **2** ·
resolved=false+fm=false **2** · resolved=false F2P-lulus-P2P-regresi **6** ·
resolved=false target-fail-murni (f2p>0,p2p=0) **8** · resolved=false campuran
(f2p>0,p2p>0) **8** · no-flip tanpa eval **4** · in-flight **1** (14534).

### F-1 — Kelas-B: repro longgar meloloskan fix yang salah (akar-METODOLOGI/yardstick, LV-01)

- **Signature:** FIX flip LULUS (patch lolos repro model), `file_match=true`, tapi
  `swebench_eval` `resolved=false` dengan F2P gagal; `fix.diff` menunjukkan fix
  mematikan gejala permukaan yang diuji repro, bukan kontrak yang dilanggar. Profil
  repro khas: **K4** (tanpa kontrol positif) ± K5 (vonis substring) — K4 = 45/52 case
  (87%) di Tabel A, sumbu dominan lintas-repo.
- **Akar:** **METODOLOGI yardstick** (repro = satu-satunya alat ukur FIX; kalau longgar,
  vonis L1 kehilangan makna) — dipisah dari akar-model murni (F-3): di sini fix model
  "sah" menurut alat ukurnya.
- **Lever:** **LV-01** (isi konkret paling didukung data: **kontrol positif / K4** —
  tidak membocorkan gold), **LV-10**, **LV-12**; bukti kausal terkuat: 11999
  (absennya K4 → false-flip yang lalu ditangkap P2P resmi).
- **Frekuensi:** terkonfirmasi autopsi **6 case**: `7746`, `12308`, `13220`, `13401`
  (Kelas-B backlog + cand=N) + era-awal `13660`, `14017`. **⏳ kandidat belum-diautopsi
  dari sel merah mekanis:** 13551, 15819, `astropy-14182`, 11019, 11283 (papan grup-1+2,
  autopsi §3 DEFERRED — bisa F-1 atau F-3), 11583 (era-lama, f2p=2 p2p=50, tak pernah
  diautopsi).
- **Anggota (terkonfirmasi):** 7746, 12308, 13220, 13401, 13660, 14017.

### F-2 — Patch over-broad / rewrite destruktif (akar-MODEL scope; superset)

- **Signature:** `resolved=false` dengan pola **F2P LULUS (bug asli terperbaiki) tapi
  P2P regresi**, ATAU error kolektif saat collection (`ImportError` → `collected 0
  items`); `fix.diff` jauh lebih besar dari perlu (gold 1 hunk vs model 4 hunk / rewrite
  modul); `line_overlap` MENYESATKAN dua arah (true di 11999 superset; false di 12907
  padahal baris fix benar — KH-13/KH-14).
- **Akar:** **MODEL** (scope discipline). Catatan desain-gate: regresi P2P **mustahil**
  ditangkap gate seketat apa pun repro-nya — gate tak menjalankan P2P (Kelas-C 11910;
  butuh perubahan kontrak eksekusi gate, bukan prompt).
- **Lever:** **LV-14** (detektor murah: mismatch jumlah region hunk gold-vs-patch
  **DUA ARAH** subset∧superset); untuk sub-kelas 11910: kandidat "gate jalankan
  sebagian P2P".
- **Frekuensi (refresh 2026-07-22):** terkonfirmasi **5 case**: `11999` (9 P2P
  NameError), `12907` (rewrite, 15 error collection), `15400` (catastrophic
  hallucination, 60+ P2P collapse), `11910` (destruktif + batas desain gate),
  **`12284` (grup-3 — varian BARU: over-broad DI DALAM satu hunk region-gold,
  guard-dihapus vs guard-dipersempit; jumlah region hunk gold==model → detektor
  mismatch-region LV-14 dua-arah TIDAK menangkapnya — blind-spot LV-14 tercatat).**
  Sel mekanis F2P-lulus-P2P-regresi juga memuat 13660×3 & 13590 (akar berbeda — F-1/F-3).
- **Anggota:** 11999, 12907, 15400, 11910, 12284.

### F-3 — Patch subset / under-general / mekanisme salah (akar-MODEL kelengkapan)

- **Signature:** `resolved=false`, `file_match=true`, patch menyentuh lokasi gold tapi
  **kurang** (hunk gold hilang → F2P gagal deterministik) atau mekanismenya salah;
  `line_overlap=true` menyesatkan (menutupi hunk yang absen).
- **Akar:** **MODEL** (kelengkapan/mekanisme), dengan kontribusi repro-under-coverage
  (repro tak menguji jalur hunk kedua — irisan dengan F-1).
- **Lever:** **LV-14** (deteksi subset region-hunk), **LV-01** (§3c(a) cakupan).
- **Frekuensi (refresh 2026-07-22):** terkonfirmasi **7 case**: `14365` (1 dari 2 hunk
  gold), `15320` (wrong mechanism `subquery=True`), `13590` (`type(value)(*gen)`),
  **+grup-3/4:** `15061` (metode DIHAPUS ≠ di-set `''`), `14534` (fallback `or`
  over-defensif), `14730` (hard `ValueError` vs gold soft `checks.Warning`), `15202`
  (drop guard `hostname is None`; case validasi repair KH-16 — kini adjudikasi adil).
  **⏳ merah baru belum-diautopsi:** 13321 (f2p=18), 14155 (f2p=3) — pasca-repair gold,
  reached VERIFY target-fail; bisa F-1/F-3.
- **Anggota:** 14365, 15320, 13590, 15061, 14534, 14730, 15202. (⏳: 13321, 14155.)

### F-4 — FIX-no-flip: model tak menghasilkan patch yang lolos repro-nya sendiri

- **Signature (operasional):** `f-dev` `verdict.json` → `phases.fix.verdict =
  "no-flip"`, `pass_l1=false`; `swebench_eval.json` & `gold_eval.json` **TIDAK ADA**
  (checker by-design tak dijalankan untuk run non-qualified). **REKLASIFIKASI dari
  papan grup-1+2 §2 "❓ reached-FIX-no-VERIFY":** `12470` & `15388` ternyata sel ini —
  checker tidak rusak; FIX-nya yang tak pernah qualified (menjawab pertanyaan-terbuka
  papan; lihat §6.2).
- **Akar:** campuran — **LV-09 terimplikasi kuat di 3 dari 4 run**: hitungan
  `No module named 'pipe_runtime'` di console FIX: `11422` r1 = **441**, `11910` r1 =
  **588**, `15388` = **232**; `12470` = **0** (⏳ sub-akar lain, belum diautopsi).
  Sesuai KH-09: JANGAN dibaca kausal tanpa buka artefak — tapi 232–588 kejadian
  di run yang gagal produksi patch adalah sinyal besar yang murah diverifikasi.
- **Lever:** **LV-09** (kirim `pipe_runtime.py` ke dunia kerja FIX); observability:
  no-flip layak label verdict sendiri di papan (bukan "tak ada eval").
- **Frekuensi (refresh 2026-07-22):** **5 run / 5 case** (semua diperiksa): 11422,
  11910(r1), 12470, 15388, **+12184** (pasca-repair gold KH-16: R qualified, FIX
  no-flip "no-diff", `pipe_runtime` hilang **260** kejadian — pola LV-09 yang sama).
- **Anggota:** 11422, 11910, 12470(⏳ akar), 15388, 12184.

### F-5 — Wrong-file mendarat di FIX — DIPERSEMPIT (KH-18): union DUA sub-akar, satu KEBAL prune

- **Signature:** `f-dev` `gold_eval.file_match=false` + `resolved=false`. **Klaim lama
  "akan punah oleh prune" DIPERSEMPIT** — wajib buka `l-dev gold_eval` untuk membelah:
  - **Sub-akar (a) — hilir Kelas-A** (l-dev `file_match=false`): recall-miss hulu;
    punah oleh `--prune-localize-miss` (dengan keying yang benar, KL-G3-2).
  - **Sub-akar (b) — FIX-wrong-file-selection, PRUNE-IMMUNE** (l-dev `file_match=TRUE`
    ∧ `qualified=true`, pointed=gold): model memilih file salah **saat menulis patch**
    padahal localize sempurna. Perbaikan recall pun takkan menyembuhkan; akar-MODEL
    fase-FIX. Counterexample: `13448` (localize tunjuk gold `base/creation.py`,
    FIX malah patch `test/utils.py`).
- **Frekuensi (refresh 2026-07-22):** **4 run** di sel mekanis: `11742` (qualified=true
  — kegagalan FIX, bukan recall), `13158` (sub-akar (a)), `13448` (sub-akar (b)),
  `13964` (re-run pasca-false-prune, FIX belum benar). Papan skor end-to-end WAJIB
  tetap menghitung yang di-prune sebagai gagal.
- **Anggota:** (a): 13158; (b): 13448; campuran/nuansa: 11742, 13964.

### F-6 — Lulus-palsu / `resolved=true` + `file_match=false`

- **Signature:** `swebench_eval.resolved=true` DAN `gold_eval.file_match=false`
  (`line_overlap=null` — jangan dibulatkan). Recall detektor ini RENDAH (lulus-palsu
  di file benar tak tersentuh — 12915/12286).
- **Frekuensi (refresh 2026-07-22):** **2 dari 40 run resolved=true**: `13658`
  (TERKONFIRMASI lulus-palsu — KH-06), `11620` (**belum diputuskan**: fix_file_match
  =false tapi 0 regresi dari 66 P2P → kandidat fix-alternatif-valid; §3b sabotase =
  prioritas re-test). **Koreksi 2026-07-22:** `11964` yang sempat di-flag audit
  sebagai kandidat lulus-palsu = **SEJATI** (flag berbasis l-dev file_match; padahal
  FIX patch-nya di file gold, fix_file_match=true).
- **Aturan deteksi (pelajaran §3a, refine bot-03):** lulus-palsu WAJIB dideteksi dari
  **FIX `gold_eval.file_match`** (patch akhir), BUKAN dari l-dev/localize file_match —
  yang terakhir OVER-FLAG.
- **Anggota:** 13658 (confirmed), 11620 (⏳ pending §3b).

### F-7 — Batas metodologi / gold-blind (bukan defek harness; JANGAN dipasangi lever)

- **Anggota & bentuk:** `13768` (F2P brittle exact-string wording log — unguessable
  gold-blind); daya-beda-F2P-rendah (13658, 13590 — n=2, "bukan angka, alasan untuk
  mengukur"); `11910` sisi gate-tak-jalankan-P2P (batas desain, lever = ubah kontrak
  gate); `11848` divergensi century (tak terjangkau sampai tahun ≥2100); `12747` &
  `13028` divergensi yang tak diukur test resmi mana pun.
- **Disiplin:** aturan katalog #6 — lever yang menyerang akar salah adalah cara
  termahal untuk belajar. Kelas ini di-CATAT untuk kejujuran papan skor, bukan untuk
  diperbaiki.

---

## §V — Fase VERIFY / eval

Fase V jarang jadi wall sejati — mayoritas "kegagalan V" ternyata reklas ke hulu (F-4)
atau environment. Denominator: 66 run f-dev.

### V-A — Checker tak menghasilkan eval KARENA no-flip (bukan bug checker) → lihat F-4

Empat run tanpa `swebench_eval.json` semuanya verdict `no-flip` (11422, 11910 r1,
12470, 15388). Tidak ada kasus "FIX qualified tapi checker diam" di korpus saat sweep.

### V-B — Spec hilang → `resolved=None` nyangkut WAIT diam-diam

- **Signature:** `swebench_checker` exit-1 "spec not found"; dashboard WAIT tanpa error
  keras. **5 case** terdampak: 11797, 13158, 15320 (era-lama, sudah diperbaiki
  fetch-spec) + **11905, 14667** (temuan audit-integritas bot-03; spec sudah
  di-fetch commit `202ded2`). Kandidat improvement: checker gagal-keras / validasi
  spec saat setup. Akar: **HARNESS-setup**.

### V-C — Crash encoding `charmap` (cp1252) checker di Windows atas output astropy

- **Signature:** checker exit-1 `UnicodeDecodeError: 'charmap'`; `swebench_eval.json`
  tak tertulis. **3 case** (12907, 14365, 14995); workaround terverifikasi
  `PYTHONUTF8=1`. Akar: **ENVIRONMENT/harness realm eval** (temuan (A)); praktis pasti
  kambuh di base non-ASCII lain — relevan untuk re-test astropy & grup non-django.

### V-D — P2P kosong by-spec → nol pagar regresi

- **Signature:** `swebench_spec.json` `PASS_TO_PASS: []`; "resolved" bersandar 100%
  pada F2P. **1 case** (`14672`). Konsekuensi operasional: untuk case ber-P2P-kosong,
  §3b patch-vs-gold WAJIB — hijau swebench sendiri tidak cukup.

### V-E — False-live / stale (sisi-tulis) → lihat R-7

Kandidat graceful-shutdown (verdict `interrupted`). Komplementer fix dashboard mtime
`9476fc6` (sisi-baca).

---

## §H — Kelas "hijau-tapi-bisa-di-enhance" (permintaan Mirza; SOP §3b/§4)

Denominator (refresh 2026-07-22): **40 run resolved=true** (38 fm=true + 2 fm=false), semua tersapu mekanis;
klasifikasi semantik di bawah hanya untuk yang §3b-nya sudah dijalankan dan terdokumentasi.

### H-1 — Hijau-ASLI, §3b selesai: patch setara/verbatim gold (baseline pembanding; no action)

- **18 case (refresh 2026-07-22):** 11049, 15790, 12497 (verbatim/byte-identik);
  14787, 15347, 14915, 14672 (†P2P-kosong, lihat V-D), 6938, 11964, 11001, 11133,
  11815, 11848 (†divergensi century tak-terjangkau), 11179, 14238, 13230
  (setara-semantik); **+grup-4 (§3b tuntas bot-03):** `13315` (mekanisme-divergen
  setara — `.distinct()` vs gold `Exists(OuterRef)`, 0 regresi), `13757`
  (sqlite-ekuivalen; †catatan subset-oracle tak-teruji, sejajar batas-metodologi).
- **Nilai analitik:** mayoritas hijau-asli dicapai **TANPA bantuan yardstick** (repro
  tetap K4; fix-space kebetulan sempit) — hijau ≠ bukti gate menggigit (11099/13230,
  LV-01). Jangan hitung sebagai validasi yardstick.

### H-2 — Hijau LEBIH KETAT dari gold

- **1 case:** `11099` (memperbaiki dua anchor, gold satu). Enhance yang mungkin:
  repro-nya sendiri tak pernah menguji anchor depan — contoh alat ukur yang tak bisa
  membedakan fix minimal vs fix model.

### H-3 — Hijau LEBIH LONGGAR / divergen dari gold (target enhance UTAMA — bahan re-test terkaya)

Semua lolos karena test resmi + repro sama-sama tak mengukur divergensinya (signature
LV-14). Per case + apa yang tak terukur:

- `12915` — `sync_to_async` dibuang → blokir event loop (tak ada test blocking).
- `12286` — fallback satu tingkat vs penelusuran bertahap (divergensi pada
  `LANGUAGES` varian-antara; KH-08).
- `13710` — dead-code `else` → `verbose_name_plural` ireguler tak dihormati.
- `13028` — penanda insidental `_state` vs prinsip `resolve_expression` (lubang laten).
- `15814` — over-select relasi proxy (`only()` diabaikan; terukur probe: 3 vs 4 kolom).
- `14995` — aliasing: `deepcopy` dibuang, mask by-reference.
- `12708` — guard `exclude=meta_*` dibuang → regresi laten `Meta.indexes/constraints`.
- `14016` — aliasing `return self/other` vs reconstruct-copy.
- `15498` — redefinisi `safe_join` tanpa containment-check → regresi keamanan
  path-traversal (tak-terukur test).
- `13447` — rename API publik tak diminta (`_build_app_dict`→`build_app_dict`).
- `12700` — subtipe minor (`type(value)(...)` vs tuple) + key rekursi.
- `12747` — 1 dari 2 hunk gold (jalur `delete_batch` hilang; repro & F2P sama-sama buta).
- **12 case.** Lever: **LV-14** (+LV-01 utk sisi repro). Ini daftar yang paling layak
  masuk urutan re-test "enhance" Mirza.

### H-4 — Hijau BELUM diperiksa §3b (jangan dihitung ke H-1/H-3 dulu)

- **8 case (refresh 2026-07-22):** `12908`, `12983` (hijau grup-1+2, §3b deferred —
  papan §3), `12453`, `10914`, `11039`, `14382`, **11620** (F-6, §3b sabotase pending),
  dan **`13033`** (solve-recovery pasca-false-prune — fix di file gold, 0 regresi,
  tapi §3b patch-vs-gold semantik belum dijalankan). Aksi murah: §3b semantik.

---

## §6 — Delta temuan sweep 2026-07-21 vs dokumentasi (bahan sinkronisasi, BUKAN edit katalog)

Dicatat di sini karena katalog/koreksi sedang ditulis bot-03 (larangan kolisi commit).
Kandidat untuk dipindahkan ke katalog oleh penulis berikutnya:

1. **Paparan LV-09 di f-dev lebih luas dari Tabel C:** metode grep identik
   (`No module named 'pipe_runtime'` per console.log) kini memberi **10 run / 8 case**
   (Tabel C terakhir: 5 run / 3 case). Anggota baru: 11283 (28), 11422 r1 (441),
   11620 (20), 11910 r2 (176), 15388 (232). Confounder KH-09 tetap berlaku penuh
   (11620 bahkan resolved=true dengan 20 kejadian) — jangan dibaca kausal; tapi
   441/588/232 pada tiga run no-flip (F-4) adalah prioritas verifikasi murah.
2. **Reklasifikasi `12470`/`15388`** dari "reached-FIX-no-VERIFY ❓" (papan §2) menjadi
   **FIX no-flip** (F-4): `phases.fix.verdict="no-flip"`, `pass_l1=false` — checker
   tidak dijalankan by-design. Item papan "kenapa checker tak hasilkan eval" terjawab;
   yang tersisa: autopsi akar no-flip 12470 (pipe_err=0).
3. **`13265` = anggota kelima keluarga KH-12** (R-1): 3/3 `syntax-fail` mislabel,
   `files/` hanya `pipe_runtime.py`, `<|tool_call>` tanpa fence (r1: 31 `call:bash` +
   9 `call:file`), hanya 2 `[exec]` di awal lalu degenerasi. Varian: sempat 2 aksi
   ter-parse sebelum loop (beda dari 14411/15851 yang 0-exec murni). Keluarga KH-12
   kini {15851, 14855, 15902, 14411, **13265**} = wall di 5 dari 17 case R-wall.
4. **`syntax-fail` = 100% artifacts-missing di korpus:** dari 27 run berlabel
   `syntax-fail`, **20 tanpa `repro.py`/`localize.md` sama sekali** dan sisanya
   kehilangan `repro.md`/format — **nol SyntaxError sungguhan teramati**. Memperkuat
   spec relabel Mirza (`repro-missing`/`vacuous-repro`/…, temuan (B) #1).
5. **Diskrepansi artefak `11797` — TERJAWAB (Mirza, 2026-07-21):** direktori
   `f-dev--django__django-11797--r1` **sengaja dihapus** (plus entrinya di
   `f-dev/runs.jsonl`) pada sesi bot-04 sebelumnya, atas keputusan Mirza, untuk
   membereskan anomali dashboard FV>L-PASS (11797 dijalankan batch gold-blind vs
   dashboard gold-aware; FV 52→51 = L-PASS). Analisis autopsinya tetap tersimpan di
   `katalog-lever.md`; artefak r-dev/l-dev 11797 utuh. Sel F-5 tetap 2 run
   (11742, 13158) dan klasifikasi 11797 di L-A tetap berlaku (bukti dari katalog +
   l-dev, bukan dari f-dev yang terhapus).
6. **Diskrepansi denominator Tabel A katalog:** section batch A2 menaikkan sampel ke
   **52 case**, tetapi section batch-A undone (lebih akhir di file) menyebut "tetap
   **44**". Pembaca berikutnya jangan mengutip salah satu tanpa cek; angka K1–K5 di
   dokumen ini memakai 45/52 (klaim terakhir yang menghitung K4).
7. **Integrasi grup-3/4 + KH-16/17/18 (2026-07-22, sumber bot-03; kelas-kelas di atas
   sudah direvisi in-place):** (a) kelas BARU **R-8 corrupt-gold** — 5/97 gold.patch
   korup, tiga di antaranya sempat salah kukandidatkan R-4 akar-MODEL (KH-16);
   (b) **Kelas-A dipertajam ke `qualified=false`** + false-prune KL-G3-2 terbukti
   mengorbankan solve nyata (13033 recovered → resolved=true) (KH-17); (c) **F-5
   dipecah dua sub-akar**, sub-akar (b) FIX-wrong-file-selection KEBAL prune (13448,
   KH-18); (d) **11964 = hijau sejati** (bukan lulus-palsu; aturan §3a: deteksi pakai
   FIX gold_eval, bukan localize); (e) paparan LV-09 f-dev kini **12 run / 10 case**
   (+12184: 260, +13448: 13 — metode grep identik); (f) blind-spot **LV-14**: 12284
   over-broad DALAM hunk region-gold, tak tertangkap detektor mismatch-region;
   (g) board 103 first-pass TUNTAS — solve genuine baru: 13757, 13315, 13033.

---

## §7 — Protokol refresh (saat grup-3/4 mendarat)

1. Jalankan ulang sweep mekanis (field §0) — atau minimal: verdict R per-run baru,
   `gold_eval.file_match` L, sel F, keberadaan eval.
2. Case R-wall baru → cek signature R-1/R-2 dulu (files/, `<|tool_call`, `[exec]`)
   SEBELUM percaya label; sisanya masuk ⏳ R-4 sampai diautopsi.
3. Case hijau baru → masuk H-4 sampai §3b dijalankan.
4. Perbarui angka di §R/§F header + funnel §0; JANGAN mengubah keanggotaan kelas
   terkonfirmasi tanpa bukti artefak (append koreksi, sebut derajatnya — SOP §6b).
5. `14534` (in-flight saat sweep) & sisa grup-3/4: klasifikasikan saat verdict final.

---

*Sumber: katalog-lever.md (LV-01..14, Kelas A/B/C, Tabel A–D, batch bot-02/03/04, A2,
backlog, grup-1+2, batch-A undone), koreksi-hipotesis.md (KH-01..15 + addenda),
rlfv-papan-skor-grup12-dan-retest.md, sop-rlfv-case-run.md §3/§5/§6, sweep mekanis
bot-04 2026-07-21 (220 r-dev / 135 l-dev / 66 f-dev run — seluruhnya, bukan sampel).*
