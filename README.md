# gemma-harness-swebench

Harness SWE-bench untuk Gemma — fresh start (hybrid: tulis baru + port selektif
komponen teruji dari `workspace-shared\smartm2m-bench`).

- **Desain kanonik:** vault `Projects/SWE-bench Gemma Harness/2026-07-18 — gemma-harness-swebench — Design Fresh Start.md`
- **Kontrak output (jantung repo):** [`docs/kontrak-output.md`](docs/kontrak-output.md) — schema_version 1.0.0
- **Metode pengembangan:** per-fase, tuntas satu-satu (REPRODUCE → LOCALIZE → FIX → VERIFY),
  UI-driven; tiap fase divalidasi dengan komparasi frontier vs Gemma pada case nyata
  tanpa hardcode case.

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

UI viewer (`python ui\server.py --root ..\artifacts --port 8766`): tabs
per fase (REPRODUCE pertama), sort desc berdasar STARTED datetime (run
terbaru case mana pun di halaman 1 — nomor rerun per-case), paging,
kolom ikon/durasi/turns. Biasanya hidup sebagai proses detached.
