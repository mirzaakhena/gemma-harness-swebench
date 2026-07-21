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

**Funnel per-case (mekanis, per 2026-07-21):** 84 case masuk REPRODUCE → **67** punya ≥1
repro qualified (**17 wall di R**) → **66** lolos LOCALIZE (**1 wall di L**: 14580) →
**63** punya run f-dev (66 − 12113 di-prune localize-miss − 13925 dihapus atas perintah
Mirza − 11797 artefak f-dev tak ditemukan, lihat §6.5) → dari 62 f-dev tuntas:
**37 resolved=true** (35 `file_match=true` + 2 `file_match=false`), **21 resolved=false**,
**4 no-flip tanpa eval** (dihitung per-run; 11910 & 13660 punya run ganda).

---

## §R — Fase REPRODUCE

REPRODUCE-wall = mode kegagalan **dominan** untuk case belum-tersentuh (papan grup-1+2:
≥6/17; sweep: 17 dari 84 case tak pernah qualified). Wall R menghentikan seluruh pipeline
— case-case ini tak menyumbang data L/F/V sama sekali.

**Denominator R:** 220 run / 84 case, semuanya tersapu mekanis. Verdict per-run:
`pass` 111 · `wrong-logic` 66 · `syntax-fail` 27 · `fail` 7 · tanpa-verdict 9.

**17 case tak pernah qualified:** 10924, 11564, 11630, 11905, 12125, 12184, 13265,
13321, 14155, 14411, 14608, 14667, 14752, 14855, 15789, 15851, 15902.

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
- **Sub-sebab terkonfirmasi (masing-masing 1 case):** salah pemetaan argumen API
  (`15789`: urutan argumen `json_script` tertukar, nol retry); precondition tak
  ditegakkan (`10924`: callable menunjuk dir yang tak pernah dibuat); predikat
  gold-unsatisfiable sungguhan (`11039` r1); setup tak lengkap (`14382` r1);
  scaffolding subprocess repro sendiri SyntaxError (`11564` r3 — overlap R-3).
- **Akar:** **MODEL** (kompetensi konstruksi repro); harness mengukur dengan benar.
- **Lever:** tidak ada lever tunggal — kandidat-ditolak tercatat (positive-branch
  precondition, n=1; PASS_OBSERVABLE friction, n=1). Yang sah: split reason bucket
  via `flip_run.json` ((B) #1).
- **Frekuensi:** verdict `wrong-logic` = **66 run** (semua tersapu); **case wall
  all-wrong-logic = 10** — terkonfirmasi akar: 15789, 10924 (+11564 di R-3);
  **⏳ belum-diautopsi: 11630, 11905 (6 run), 12184, 13321, 14608, 14667, 14155
  (grup-3, baru mendarat)** — 7 case ini kandidat R-4 tapi bisa saja R-3/lainnya;
  jangan dikutip sebagai akar-model sebelum dibedah.
- **Anggota (terkonfirmasi):** 15789, 10924. (⏳: 11630, 11905, 12184, 13321, 14608, 14667, 14155.)

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
- **Frekuensi:** case-level terdokumentasi **5**: `11797`, `13158`, `13925`, `11742`,
  `12113`. Sweep per-run: run L-qualified-terakhir ber-`file_match=false` = **7 case**,
  dua tambahan yang WAJIB dibaca dengan nuansa:
  - `11620` — file_match=false di L DAN F, tapi **resolved=TRUE** (F2P + 66 P2P lolos,
    0 regresi). Kandidat "fix-alternatif-lokasi-valid" — butuh §3b sabotase (papan §3).
    Kelas-A tidak selalu berakhir merah.
  - `11964` — r2–r15 (kampanye eksperimen era-lama) file_match=false, tapi **FIX
    memakai r1 yang file_match=true** → hijau-asli. **BUKAN Kelas-A end-to-end.**
    Pelajaran metodologi: heuristik "run qualified terakhir" menyesatkan pada case
    ber-kampanye; yang menentukan adalah run yang benar-benar jadi input FIX.
- **Sub-split gold-unguessable vs kelalaian (permintaan handoff):** baru **1 case yang
  dinilai eksplisit**: `12113` = **gold-unguessable** (problem statement = traceback
  generic-layer; gold di `sqlite3/creation.py::test_db_signature` yang tak tersebut —
  butuh domain-knowledge). 4 case lain (11797, 13158, 13925, 11742) **belum dinilai
  per-kasus** pada sumbu ini — jangan diekstrapolasi. Menilainya murah (baca problem
  statement vs file gold) dan layak masuk agenda re-test.
- **Anggota:** 11797, 13158, 13925, 11742, 12113 (+nuansa: 11620, 11964).

### L-B — Trace-pool kosong: repro subprocess mematikan LOCALIZE sebelum LLM (akar-HARNESS)

- **Signature:** `verdict.json` L `pass_l1=false` verdict `syntax-fail` dengan failures
  "artefak wajib tidak ada: localize.md"; `files/` **kosong total**; `events.jsonl`
  event `abort` "trace pool is empty"; deterministik 3/3 (retry mustahil menolong).
  Prasyarat: repro input berbentuk `subprocess.run([sys.executable, ...])`.
- **Akar:** **HARNESS** (trace-injection tidak mengikuti fork ke subprocess anak) —
  model TAK PERNAH dipanggil. Gap kontrak lintas-fase: qualified-R tak menjamin
  traceable-L. Konsekuensi hilir LV-12 yang belum tercatat sebagai entri.
- **Lever:** bug-robustness tak-bernomor (katalog batch bot-02); syarat naik ≥3 case.
  Rekomendasi tercatat: follow-fork trace ATAU gate R menambah cek in-process.
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
- **Frekuensi:** terkonfirmasi **4 case**: `11999` (9 P2P NameError), `12907`
  (rewrite, 15 error collection), `15400` (catastrophic hallucination, 60+ P2P
  collapse), `11910` (destruktif + batas desain gate; r1 no-flip, r2 F2P lulus 1 P2P
  gagal). Sel mekanis F2P-lulus-P2P-regresi juga memuat 13660×3 & 13590 (akar berbeda —
  F-1/F-3).
- **Anggota:** 11999, 12907, 15400, 11910.

### F-3 — Patch subset / under-general / mekanisme salah (akar-MODEL kelengkapan)

- **Signature:** `resolved=false`, `file_match=true`, patch menyentuh lokasi gold tapi
  **kurang** (hunk gold hilang → F2P gagal deterministik) atau mekanismenya salah;
  `line_overlap=true` menyesatkan (menutupi hunk yang absen).
- **Akar:** **MODEL** (kelengkapan/mekanisme), dengan kontribusi repro-under-coverage
  (repro tak menguji jalur hunk kedua — irisan dengan F-1).
- **Lever:** **LV-14** (deteksi subset region-hunk), **LV-01** (§3c(a) cakupan).
- **Frekuensi:** terkonfirmasi **3 case**: `14365` (1 dari 2 hunk gold), `15320`
  (wrong/narrower mechanism, tak set `subquery=True`), `13590` (`type(value)(*gen)`
  merusak tuple, 1 P2P).
- **Anggota:** 14365, 15320, 13590.

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
- **Frekuensi:** **4 run / 4 case** (semua diperiksa): 11422, 11910(r1), 12470, 15388.
- **Anggota:** 11422, 11910, 12470(⏳ akar), 15388.

### F-5 — Wrong-file mendarat di FIX (hilir Kelas-A; kelas yang akan PUNAH oleh prune)

- **Signature:** `f-dev` `gold_eval.file_match=false` + `resolved=false`. Hulu-nya L-A.
- **Frekuensi:** **2 run** di korpus (`11742` f2p=2 p2p=43, `13158` f2p=1) — keduanya
  pra-`--prune-localize-miss`; `12113` sudah ter-skip benar oleh prune. Papan skor
  end-to-end WAJIB tetap menghitung yang di-prune sebagai gagal.
- **Anggota:** 11742, 13158.

### F-6 — Lulus-palsu / `resolved=true` + `file_match=false`

- **Signature:** `swebench_eval.resolved=true` DAN `gold_eval.file_match=false`
  (`line_overlap=null` — jangan dibulatkan). Recall detektor ini RENDAH (lulus-palsu
  di file benar tak tersentuh — 12915/12286).
- **Frekuensi:** **2 dari 37 run resolved=true**: `13658` (TERKONFIRMASI lulus-palsu —
  daya beda F2P crash-vs-tidak-crash + regresi diam, KH-06), `11620` (**belum
  diputuskan**: 0 regresi dari 66 P2P → kandidat kuat fix-alternatif-lokasi-valid;
  §3b sabotase = item re-test prioritas papan §3).
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
  keras. **3 case** terdampak (11797, 13158, 15320 — setup era-lama), sudah diperbaiki
  (fetch spec + re-verify). Kandidat improvement: checker gagal-keras / validasi spec
  saat setup. Akar: **HARNESS-setup**.

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

Denominator: **37 run resolved=true** (35 fm=true + 2 fm=false), semua tersapu mekanis;
klasifikasi semantik di bawah hanya untuk yang §3b-nya sudah dijalankan dan terdokumentasi.

### H-1 — Hijau-ASLI, §3b selesai: patch setara/verbatim gold (baseline pembanding; no action)

- **16 case:** 11049, 15790, 12497 (verbatim/byte-identik); 14787, 15347, 14915, 14672
  (†P2P-kosong, lihat V-D), 6938, 11964, 11001, 11133, 11815, 11848 (†divergensi
  century tak-terjangkau), 11179, 14238, 13230 (setara-semantik).
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

- **7 case:** `12908`, `12983` (hijau grup-1+2, §3b deferred — papan §3), `12453`,
  `10914`, `11039`, `14382`, plus **11620** (F-6, §3b sabotase pending), dan setiap
  hijau grup-3/4 yang akan datang. Aksi murah: §3b patch-vs-gold semantik.

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
5. **Diskrepansi artefak `11797`:** autopsi backlog mencatat FIX 11797 resolved=false,
   tetapi direktori `f-dev--django__django-11797--r*` **tidak ditemukan** saat sweep.
   Sel F-5 karenanya berisi 2 run (11742, 13158), bukan 3. Perlu klarifikasi bot-03/
   Mirza (terhapus? tak pernah ada?).
6. **Diskrepansi denominator Tabel A katalog:** section batch A2 menaikkan sampel ke
   **52 case**, tetapi section batch-A undone (lebih akhir di file) menyebut "tetap
   **44**". Pembaca berikutnya jangan mengutip salah satu tanpa cek; angka K1–K5 di
   dokumen ini memakai 45/52 (klaim terakhir yang menghitung K4).

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
