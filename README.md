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
- `pipe_runtime.py` (r33): modul `App` di-ship harness ke `.pipe/` SEMUA
  dunia eksekusi (container kerja, fresh pre-check, gate/flip) — start &
  settle baseline otomatis di tiap ready (termasuk tiap reload), semua
  output child di-echo `[app] ` (kelas race-baseline & trace-tertelan
  dipindah dari disiplin prompt ke fisika modul); kontrak rule:app-runtime

UI viewer (`python ui\server.py`, port 8766): tabs per fase (REPRODUCE
pertama), sort desc, paging, kolom ikon/durasi/turns.
