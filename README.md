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
- UTF-8 tanpa BOM, newline LF — di-enforce emitter (jebakan: PowerShell default UTF-16).
- Append-only: rerun = `r<N+1>` = direktori baru; dir lama tidak dimutasi.
- Test dari hari 1: `python -m pytest` dari root `main\`.
