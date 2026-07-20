# Eksekusi Implementasi Stage FIX (desain & plan SUDAH disetujui/siap)

**Date:** 2026-07-20 10:05 (WIB)
**Repo kerja:** C:\Users\Mirza\workspace\gemma-harness-swebench\main
**Branch:** main (HEAD sebelum handoff: lihat git log — commit terakhir sesi bot-04: draft plan + handoff ini)
**Dari → Ke:** bot-04 → sesi berikut (bot mana pun; Mirza ganti akun Claude, sisa kuota mingguan 4%)
**Lanjutan dari:** `.handoff/202607200745-prompt-fix-phase-kickoff.md`

---

## 1. Tujuan Handoff

Brainstorm + spec + plan fase FIX TUNTAS di sesi bot-04 (2026-07-20 pagi).
Sesi berikut tinggal MENGEKSEKUSI implementation plan task-per-task (TDD,
subagent-driven), lalu smoke run f-dev case pertama.

## 2. Yang Sudah Selesai (sesi bot-04, 2026-07-20)

a. **Brainstorm desain stage FIX dgn Mirza TUNTAS** — semua keputusan
   DISETUJUI eksplisit, tercatat vault **"Desain Stage FIX — Keputusan
   Brainstorm (gemma-harness-swebench)"** (§A dua realm · §B loop
   harness-driven iterasi kandidat, Gemma fresh context per attempt ·
   §C ber-bash, harness memilihkan kandidat, seed [problem + repro.md +
   isi repro.py + kandidat aktif saja] · §D kontrak output & vonis
   [bukti-dulu, pre-check pair dunia segar, standar tunggal, fix.diff
   via git diff harness] · §E riset gold: 18/18 single-file, 6/18
   multi-hunk → multi-file = non-goal · §F pagar edit / populasi 13
   case (+12747) / f-dev r1 append-only / budget pola L · §G mandat
   dashboard-first · §H spec approved).
b. **Spec formal DISETUJUI Mirza**:
   `docs/superpowers/specs/2026-07-20-fix-stage-design.md` (commit fd9be89).
c. **Dashboard tab FIX LIVE** (mandat Mirza dikerjakan duluan): commit
   78ef1f3, 287→292 test hijau, viewer 8766 sudah restart & terverifikasi.
d. **Implementation plan DRAFT ditulis** (subagent, sudah baca kode nyata):
   `docs/superpowers/plans/2026-07-20-fix-stage.md` — 9 task TDD
   (protokol sesi FIX → fix_gates pure → fix_patch_runner →
   fix_prompt.md → helper driver → driver main() → run_fix_gates →
   fix_gold_eval → make_fix_campaign). Di-commit bersama handoff ini.
e. Plane SMARTXRESE-374: comment [bot-04] kickoff FIX.

## 3. SEDANG

— (berhenti bersih; tak ada file setengah-edit; belum ada kode product
FIX yang ditulis; belum ada run f-dev.)

## 4. Blocker

—

## 5. Yang Akan Dikerjakan (AKAN)

1. **Review 3 asumsi plan** (subagent penulis plan mengambil 3
   interpretasi — sahkan/koreksi sebelum eksekusi, bila ragu tanya
   Mirza): (a) dua arg input `--input-localize-files` +
   `--input-repro-files` (bukan satu `--input-files` pola L) karena
   candidates.md hidup di run L sedang repro.md+repro.py di run R;
   (b) `file_match` eval gold = SUBSET (⊆ file gold) bukan `==`,
   karena gold lazim ikut menyentuh test file; (c) `fix_prompt.md`
   TANPA marker rule:/detail dulu (rule_catalog hardcode ke
   reproduce_prompt.md; enforcement FIX sudah mekanis penuh).
2. **Eksekusi plan task 1–9** via subagent-driven development (fresh
   subagent per task, review antar task); `python -m pytest` hijau
   dari root main\ per commit; trailer `Agent: <bot>`.
3. **Smoke run f-dev case pertama** (usul: 13660 — L 3/3 bullseye
   identik, sinyal kuat; atau 11422 happy path historis). SEBELUM run
   Gemma: gpu_check waiting==0 FOREGROUND terpisah (lihat §7 catatan).
4. Lapor Mirza per milestone via Telegram; catat run di vault (usul:
   note baru "F-dev Log — fase FIX" pola R-dev Log).

## 6. Referensi (urutan baca di awal)

| Referensi | Kapan |
|---|---|
| Vault `Desain Stage FIX — Keputusan Brainstorm (gemma-harness-swebench)` | Di awal — SEMUA keputusan Mirza |
| `docs/superpowers/specs/2026-07-20-fix-stage-design.md` | Di awal — spec disetujui |
| `docs/superpowers/plans/2026-07-20-fix-stage.md` | Di awal — plan eksekusi 9 task |
| `docs/prinsip-pengembangan.md` + `docs/kontrak-output.md` | Di awal — aturan baku |
| `.handoff/202607200745-prompt-fix-phase-kickoff.md` §9 | Di awal — anti-patterns carry-forward (python -m, CRLF, gpu_check, docker env testbed, dsb.) |
| Vault `Paket Bahan Sesi Keputusan FIX — 2026-07-19` + R-dev Log | Kondisional — konteks sejarah |

## 7. Catatan Lain

- Commit sesi bot-04: 78ef1f3 (tab FIX) · fd9be89 (spec) · <commit ini>
  (plan draft + handoff). Semua trailer `Agent: bot-04`. Belum di-push
  (tak ada remote).
- Keputusan TERBUKA warisan (JANGAN dieksekusi tanpa Mirza; dari
  handoff sebelumnya): eskalasi R-a/R-b · bentuk lever predikat-probe
  LOCALIZE · 11797 tetap parkir · backlog non-FIX (schema 1.1, dsb.).
- Viewer 8766 hidup detached (restart: `Start-Process -WindowStyle
  Hidden python -ArgumentList 'ui\server.py','--root','..\artifacts','--port','8766'` dari main\).
- Endpoint Gemma: http://10.8.0.86:8000/v1 (google/gemma-4-31B-it) —
  SERING FLIP, cek gpu_check dulu:
  `python C:\Users\Mirza\workspace-shared\smartm2m-bench\swe\harness-uplift\swebench-original\gpu_check.py`.
- Telegram Mirza chat_id 1121398977 — teach-me utk penjelasan, ringkas
  utk status, inline buttons utk pertanyaan, immediate-reply sblm tool.
- Plane: project c42a6f66-c1b0-41ea-93b3-61ae98ff9642, SMARTXRESE-374.
