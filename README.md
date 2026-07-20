# gemma-harness-swebench

Harness SWE-bench untuk Gemma — fresh start (hybrid: tulis baru + port selektif
komponen teruji dari `workspace-shared\smartm2m-bench`).

- **Desain kanonik:** vault `Projects/SWE-bench Gemma Harness/2026-07-18 — gemma-harness-swebench — Design Fresh Start.md`
- **Kontrak output (jantung repo):** [`docs/kontrak-output.md`](docs/kontrak-output.md) — schema_version 1.0.0
- **Metode pengembangan:** per-fase, tuntas satu-satu (REPRODUCE → LOCALIZE → FIX → VERIFY),
  UI-driven; tiap fase divalidasi dengan komparasi frontier vs Gemma pada case nyata
  tanpa hardcode case.

### Baca ini dulu kalau kamu menerima handoff

| Dokumen | Isi |
|---|---|
| [`docs/sop-rlfv-case-run.md`](docs/sop-rlfv-case-run.md) | **SOP menjalankan & membedah case.** Prosedur eksekusi, aturan GPU, protokol pemeriksaan wajib (lulus palsu, kualitas repro, eksperimen sabotase), disiplin epistemik, anti-pattern. Mulai dari sini. |
| [`docs/prinsip-pengembangan.md`](docs/prinsip-pengembangan.md) | Arah & keputusan Mirza; definisi "qualified setara"; aturan bahasa; higiene prompt. |
| [`docs/katalog-lever.md`](docs/katalog-lever.md) | Backlog perbaikan harness ber-ID (LV-01…LV-14) + tabel frekuensi kelas kegagalan. **Semua berstatus BELUM DITERAPKAN** — rekomendasi, bukan instruksi kerja. |
| [`docs/koreksi-hipotesis.md`](docs/koreksi-hipotesis.md) | Klaim yang pernah kami pegang lalu dibantah (KH-01…KH-13), beserta buktinya. Baca supaya tidak mengulang klaim yang sudah mati. |

**Peringatan yang paling sering salah dibaca:** `resolved=true` dari `swebench_checker`
berarti "tidak ada test resmi yang gagal", **bukan** "patch benar". Sudah terbukti tiga
kali berbeda (12915, 13658, 12286). Lihat SOP §4.

## Struktur dunia (satu folder = satu dunia)

```
gemma-harness-swebench\
├── main\               ← repo ini (main branch)
├── worktree-<nama>\    ← git worktree add ..\worktree-<nama> -b <nama>
└── artifacts\          ← SEMUA data run; DI LUAR git tree; TANPA symlink
```

`artifacts\` tidak pernah disentuh operasi git (worktree remove/checkout) —
akar insiden hilangnya 52 dump RLF (2026-07-18) mati by construction.

## Aturan repo

- Emitter tunggal: hanya `harness/emit.py` yang boleh menulis
  `events.jsonl` / `verdict.json` / `runs.jsonl` / `campaign.json`.
- UTF-8 tanpa BOM, newline LF — di-enforce emitter (jebakan: PowerShell default UTF-16;
  jebakan kedua yang terbukti: `text=True` subprocess Windows menulis CRLF ke pipe docker).
- Append-only: rerun = `r<N+1>` = direktori baru; dir lama tidak dimutasi.
- Test dari hari 1: `python -m pytest` dari root `main\`.

## Driver REPRODUCE Gemma — mekanisme terpasang (2026-07-19)

Kontrak `harness/stages/reproduce_prompt.md` = **dua-tier** ber-marker:
blok `rule:` dirender ke model + injectable; blok `detail:` injeksi-only
via `rule_catalog.py` (katalog = system prompt itu sendiri, kutipan verbatim,
drift-guard test). Render: `rule_catalog.core_contract()`.

Mekanisme driver (`run_reproduce_gemma.py`), semua lahir dari kelas kegagalan
nyata r7–r29 (riwayat: vault `R-dev Log — fase REPRODUCE`):

- bukti-dulu: DONE ditolak sampai `REPRO_STATUS: FAIL` disaksikan
- eksekusi `repro.py` SELALU di sandbox segar (`is_repro_run`) — vonis
  mid-loop = kebenaran gate; state bengkel tak bisa menipu
- `PASS_OBSERVABLE` diverifikasi grep ke source repo (exclude script;
  marker sendiri sah hanya bila DICETAK script)
- pre-check DONE = 2 run sandbox segar (mirror gate idempoten)
- judge-review fresh-context saat DONE (advisory; vonis tetap gate)
- format reminder, next-step nudge, repeated-error note, checkpoint
  known-good (`files/repro-first-fail.py`), telemetri retry beralasan
- gate + flip: `run_repro_gates.py --gold` (L2 = definisi qualified);
  problem statement case: `cases/problems/<case_id>.txt`
- `pipe_runtime.py` (r33+): modul `App` di-ship harness ke `.pipe/` SEMUA
  dunia eksekusi (container kerja, fresh pre-check, gate/flip) — start &
  settle baseline otomatis di tiap ready (termasuk tiap reload), semua
  output child di-echo `[app] ` (kelas race-baseline & trace-tertelan
  dipindah dari disiplin prompt ke fisika modul); kontrak rule:app-runtime.
  API race-proof by construction: cursor anti stale-match (850b345),
  auto-settle saat match mengonsumsi ready (a7add92), grace window utk
  pengumuman restart (0c3ecca); wait_* return bool & never raise (86b2617)
- standar token TUNGGAL baris-eksak (`exact_status`): "FAIL tersaksikan"
  mid-loop == pre-check pair == gate; token_format_note saat trailing text
- telemetri pair: event done-rejected pair membawa detail terstruktur
  (status/exit/tail kedua run) + output pair di-log `[exec-pair]`
- kontrak DEFAULT = ultra-slim (self-contained & repeatable detail-only,
  dijaga fisika; keputusan Mirza pasca-A/B dua case); varian full via
  `--contract-variant full` (A/B tooling)

Status case REPRODUCE (2026-07-19): 11422 STABIL (streak 3, r39–r41);
11999 STABIL 6/6 (A/B slim vs full); 11964 STABIL 3/3 (adversarial).
Survey 5 case fail-harness-lama TUNTAS: 11910 2/3; 11797 & 13220 pra-lever
0/3 (kelas predikat-literal-rapuh & over-testing gold-unsatisfiable) →
pasca Paket Predikat (5ffbd35: rule:predicate-from-witnessed-output +
rule:scope-minimal-predicate di CORE) keduanya 3/3; 12308 & 13401 3/3
langsung. Riwayat lengkap: vault R-dev Log; distilasi metode:
vault "Prinsip Stabilisasi REPRODUCE".

## Fase LOCALIZE — dev-loop ronde 2 (2026-07-19)

Boundary (framing Mirza): **product = harness + model, gold-blind total**;
evaluasi kebenaran vs gold hidup TERPISAH di lapisan test-system
`eval/localize_gold_eval.py` (CLI `--case --rerun --gold`; output
`gold_eval.json` per run). **Kriteria qualified = SHORTLIST** (keputusan
Mirza 2026-07-19, b127f4c): ada kandidat candidates.md ∈ file yang
disentuh gold — fase FIX mengiterasi shortlist; chosen file + overlap
baris = advisory; pagar mekanis 2–3 kandidat. Gate product
(`run_localize_gates.py`) murni L1. Input beku per case = repro Gemma
qualified dari fase R (`--input-files`).

Status batch 7 case (@3 run, streak-minimum): 11422 sanity ✅ · 11999 3/3 ·
12308 3/3 (situs identik + overlap true 3×) · 13401 3/3 · 13220 3/3 ·
11964 1/3 · 11797 0/3 — total 19 run, 14 qualified (74%). Dua case gagal
sekelas "salah lapisan" (alternative-fix-site / manifestation-layer).

Lever L (2026-07-19, dua case bandel; detail vault R-dev Log):
- L#1 rule kontrak definition-site-ownership + probe lintas-lapisan
  (f8c1d9f): 11964 1/3, 11797 0/3 — NOL efek (rule pasif).
- L#2 enumerasi kandidat mekanis (f69e86a): candidates.md wajib (≥2
  kandidat, file beda, evidence+expectation, file ada; localize.md ∈
  kandidat) — mekanisme 100% patuh, kebenaran NOL membaik (11964 0/3,
  11797 0/3): file akar tak pernah masuk bidang pandang model.
- Telemetri kaya driver L (4c25b56): retry beralasan verbatim.
- Dashboard: satu status gabungan L1+gold_eval (f9a4c7b, keputusan
  "lengkap+rapi+benar"); kolom case+run dipecah (069fd0e).
- L#3 trace-injection (d960096, bot-04): harness eksekusi repro.py di
  container segar di bawah sys.settrace (localize_tracer.py) → pool file
  repo tereksekusi diinject ke pesan user pertama + enforce candidates ⊆
  pool (localize_trace.py, driver v2; gagal trace = abort; artefak
  files/trace_pool.json). Base-world murni. HASIL: 0/6 (11964 0/3, 11797
  0/3) — pool 201 file memuat file gold by construction, tapi file
  favorit framing model ikut tereksekusi → konstrain keanggotaan tak
  pernah menggigit. Kesimpulan lintas 4 kondisi (pra/L#1/L#2/L#3): akar
  = PRIOR framing saat memilih lapisan, bukan bidang pandang. Verdict
  lengkap: vault R-dev Log "VERDICT L#3". Arah berikut menunggu Mirza
  (kandidat: selector fresh-context / sinyal pembeda intra-pool / parkir
  kelas framing).

## Fase FIX — stage baru (2026-07-20), kampanye `f-dev`

Arsitektur (spec `docs/superpowers/specs/2026-07-20-fix-stage-design.md`,
keputusan Mirza): **harness-driven iterasi kandidat** — harness mengambil
shortlist `candidates.md` dari run L qualified (urutan tulis, tanpa
prioritas) dan mencoba SATU kandidat per attempt; tiap attempt = sesi
Gemma **fresh context** + container kerja BARU (pristine by construction).
Model TIDAK pernah melihat kandidat lain (anti context-pollution — akar
kegagalan pemilihan lapisan di fase L diambil alih harness).

- **Seed per attempt**: problem statement + `repro.md` verbatim + **isi
  `repro.py`** (pelajaran P21: model melihat lembar ujiannya) + kandidat
  AKTIF saja.
- **Bukti-dulu**: DONE ditolak sampai driver MENYAKSIKAN `repro.py`
  mencetak `REPRO_STATUS: PASS` (standar token baris-eksak `exact_status`).
- **Pre-check DONE = vonis dunia segar**: harness `git diff` container
  kerja → apply ke container SEGAR → `repro.py` BEKU 2× (pair) → keduanya
  PASS. State bengkel tak pernah dipercaya; repro vonis selalu salinan
  beku artefak fase R.
- **Pagar edit mekanis**: diff sah = hanya menyentuh file kandidat aktif
  (prompt memakai scope positif, enforcement di evaluator).
- **Standar tunggal**: `fix_patch_runner.evaluate_patch_in_fresh_world`
  adalah SATU definisi "patch sah + flip" — dipakai pre-check driver DAN
  gate. Vonis milik harness: driver tak menulis verdict, `run_fix_gates`
  yang menulis (`flip | no-flip | timeout | abort`).
- **Realm dev (gold)**: `eval/fix_gold_eval.py` — file_match + line_overlap
  advisory, penangkap false-PASS. TIDAK pernah diumpankan ke loop model.

Modul: `harness/stages/fix_gates.py` (pure) · `fix_patch_runner.py`
(docker) · `run_fix_gemma.py` (driver) · `run_fix_gates.py` (gate) ·
`fix_prompt.md` (kontrak ultra-slim) · `eval/fix_gold_eval.py` ·
`harness/make_fix_campaign.py` (13 case populasi awal).

**Invokasi WAJIB `python -m` dari root `main\`** (bukan
`python harness/stages/<x>.py` — docstring modul masih menulis pola lama):

```
python -m harness.make_fix_campaign
python -m harness.stages.run_fix_gemma --case <id> --rerun <N> --image <img> \
    --input-localize-files <dir files run L qualified> \
    --input-repro-files <dir files run R qualified> \
    --problem-file cases/problems/<id>.txt
python -m harness.stages.run_fix_gates --case <id> --rerun <N> --image <img> \
    --input-repro-files <dir files run R qualified>
python -m eval.fix_gold_eval --case <id> --rerun <N> --gold cases/gold/<id>/gold.patch
```

Status: **smoke run pertama TUNTAS** — `f-dev--django__django-13660--r1`
menang di kandidat #1 (`shell.py`, 8 turn), gate `flip`, gold eval
file_match+overlap TRUE (`exec(cmd)` → `exec(cmd, {})`, situs file/baris
sama dengan gold). **KOREKSI (checker L2, 2026-07-20):** klaim
"gold-equivalent" di atas SALAH — checker SWE-bench resmi memvonis
`resolved=false` untuk run ini (2 regresi P2P: `test_command_option_globals`,
`test_stdin_read_globals` — gold menulis `exec(cmd, globals())`, Gemma
menulis `exec(cmd, {})`, dict kosong bukan `globals()`). L1 (flip) dan
gold_eval (file/line match) sama-sama tak menangkap ini — hanya checker L2
(FAIL_TO_PASS/PASS_TO_PASS resmi) yang menangkap. Detail: vault
`F-dev Log — fase FIX` § "Checker L2 live". Riwayat per-run: vault
`F-dev Log — fase FIX`.

UI viewer (`python ui\server.py --root ..\artifacts --port 8766`): tabs
per fase (REPRODUCE → LOCALIZE → **FIX and VERIFY**; stage pipeline selalu
tampil walau belum ada run), sort desc berdasar STARTED datetime (run
terbaru case mana pun di halaman 1 — nomor rerun per-case), paging, kolom
ikon/durasi/turns, panel infografik status per stage. Biasanya hidup
sebagai proses detached. Tab kampanye `f-*` berlabel **"FIX and VERIFY"**
karena VERIFY (checker L2) hidup sebagai lapisan kedua di dalam tab yang
sama, bukan tab terpisah (lihat status 2-lapisan di bawah).

**KNOWN ISSUE dashboard (2026-07-20) — SELESAI.** Bug lama (`case_status()`
memetakan verdict `"flip"` ke default FAIL padahal baris tabel menampilkan
`✅ flip`) sudah diperbaiki bersamaan dengan implementasi status 2-lapisan
di bawah (`case_status` sekarang eksplisit menangani `flip` via
`pass_l1`/`_fix_verify_status`).

## Aturan status 2-lapisan (keputusan Mirza 2026-07-20) — TERIMPLEMENTASI

Status dashboard kampanye `f-*` = **AND dua lapisan judgment**:

| Lapisan | Isi | Field |
|---|---|---|
| L1 — product harness (gold-blind) | FIX: repro flip | `pass_l1` (`verdict.json`) |
| L2 — development (SWE-bench checker ASLI) | resolved? via FAIL_TO_PASS / PASS_TO_PASS resmi | `resolved` (`swebench_eval.json`) |

- Product FAIL → FAIL. Product PASS + L2 FAIL → **tetap FAIL** (kategori
  `verify-fail`). PASS hanya bila keduanya lulus.
- **swe_bench checker asli dibangun sebagai SATU modul** (SRP: satu alasan
  berubah), hidup di realm dev (`eval/`), TIDAK ditanam inline di
  driver/gate FIX — product FIX tetap gold-blind (yardstick repro flip),
  swe_bench = pengukuran dev, tak pernah diumpan balik ke loop model.
- Preseden pola: fase LOCALIZE (`eval/localize_gold_eval.py` memakai gold di
  development; product LOCALIZE tetap gold-blind dgn kriteria SHORTLIST).

**Invokasi (dari root `main\`):**

```
python -m eval.fetch_swebench_spec --case <id> [--case <id> ...]
python -m eval.swebench_checker --case <id> --rerun <N>
```

`fetch_swebench_spec` membekukan `cases/gold/<id>/swebench_spec.json` dari
dataset HF SWE-bench_Lite sekali per case (append-only, sama seperti spec
gold lain). `swebench_checker` menjalankan grading resmi SWE-bench di
container Epoch (`ghcr.io/epoch-research/swe-bench.eval.*`) untuk satu run
FIX beku dan menulis `../artifacts/f-dev/f-dev--<id>--r<N>/swebench_eval.json`
(+ `files/swebench_test_output.log`) — **tidak pernah menyentuh
`verdict.json`** (emitter tunggal fase FIX tetap `harness/emit.py`;
checker L2 murni realm dev, read-only terhadap verdict).

**5 state status dashboard** (`ui/server.py:case_status` /
`_fix_verify_status`):

| Status | Arti |
|---|---|
| `PASS` | `pass_l1` (flip) DAN `resolved=true` — lulus L1 + L2 |
| `FAIL` (`verify-fail`) | `pass_l1` TRUE tapi `resolved=false` — L1 lulus, L2 gagal (regresi P2P / F2P / patch gagal apply) |
| `FAIL` (alur lama) | product FAIL biasa (no-flip/timeout/abort) — L2 tak relevan |
| `WAIT` | product PASS tapi `swebench_eval.json` belum ada — menunggu `swebench_checker` dijalankan (bukan FAIL palsu) |
| `ANOMALY` | product FAIL tapi `resolved=true` — kontradiksi sinyal, ditandai menonjol utk autopsi manual |
