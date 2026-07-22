# Tutup papan validasi G2 + agenda desain G3 (R15, R14+N3, R17/LV-13a)

**Date:** 2026-07-22 23:58 (WIB)
**Repo kerja:** /Users/mirza/Workspace/gemma-harness-swebench/main (macOS, arm64)
**Branch:** main (HEAD: 9777148)
**Dari → Ke:** claude-mac (sesi maraton retest+G2) → sesi baru (Mac ini)
**Lanjutan dari:** `.handoff/202607221858-prompt-pindah-mesin-macos.md` + rantai §-A0..§-A0g di [[urutan-retest-lever]]
**Plan terkait:** [[rekomendasi-lever-dari-taksonomi]] §7 (G2-baru TERPASANG); G3 = agenda sesi baru

---

## 1. Tujuan Handoff

Sesi ini menuntaskan: rate-gating G1 (§-A0f), pemasangan & validasi G2-baru (N1/N4/R12/N2
+ infra-abort + fix cap), dan konsolidasi 6 diagnosa subagent → katalog/KH. Sesi baru:
**(1) tutup papan validasi G2, (2) R15 via subagent, (3) diskusi draft desain R14+N3
dengan Mirza, (4) desain R17/LV-13a setelahnya.** STOP eksekusi run baru (keputusan
Mirza) — antrean §-A0g beku sampai keputusan berikutnya.

## 2. Konteks Proyek

Harness SWE-bench Gemma, pipeline gold-blind R→L→F→V, vonis rate-based k/n (KH-20/22),
wasit L2. Endpoint Gemma `10.8.0.86:8000` EKSKLUSIF Mirza → izin **maks 7 paralel**
(`--parallel N` di batch runner, commit `e3bc95a`). Rezim mesin: `mac-arm64-rosetta`.
Papan rate G1: `artifacts/papan-skor-rate-origin-r1-mac-g1.md` (origin 2/5, 0/5, 0/5,
1/5; kanari stabil 9/9).

## 3. Yang Sudah Selesai (SUDAH) — sesi ini

**Lever terpasang (semua ter-commit, suite 596 hijau):**
- `e055f50` fix path backslash batch runner (Mac) · `e3bc95a` mode `--parallel N`
- `b8fb62b` **N2** audit evidence↔file LOCALIZE (+`d41b116` fix whitelist emit) —
  smoke terbukti: 12184 l-r3 kandidat#1 → resolvers.py (file gold)
- `106d517` **N1** reply-hash watcher FIX (first firing: 11910 r12, turns_saved=25) +
  **N4** attempt-lock relaksasi + **R12** timeout/retry transport FIX
- `5305e00` **fix cap MAX_RERUN** = percobaan SAH saja (`is_void_infra_run`,
  `valid_rerun_attempts`, CLI `--max-rerun`)
- `9777148` **infra-abort**: `chat_transport.py` util bersama, preflight ping, salvage,
  verdict `infra-abort` di gates R/L (marker `infra_abort.json` cocok dgn batch runner)

**Docs/epistemik:** `585de71` §-A0f (papan G1) · `609116d` §7 re-prioritisasi G2 ·
`df61179`+`1d63606` KH-21 + 2 spesimen loop degenerat · `673dee3` konsolidasi 4 diagnosa
+ KH-22 + §-A0g · katalog: entri void-infra, varian-3 cacat evidence (11910), weak-oracle
pasca-N2 (12184 r13), intra-reply batch-repetition (11422 r9, catat-only).

**Validasi G2 (27 draw, `--parallel 6`+lane):** SELESAI kecuali 1 (lihat §4). State:
`artifacts/validasi-g2-mac-p1.json/.log` (24 draw: 15388/11422/11910 ×3 + 5 kanari ×3),
`artifacts/validasi-g2-mac-p2-12184.json` (3 draw rantai-N2). Hasil kunci yang sudah
terbaca: **12184 rantai-N2 = r13✗(satu-baris-dari-gold, weak-oracle) r14✗ r15✓ BERSIH**;
11910 r10/r11 ✗ signature identik (r12 dgn N1-cut belum kubaca); kanari & 15388 belum
kubaca dari state.

## 4. Yang Sedang Dikerjakan (SEDANG)

- **11422 r10 attempt-2 in-flight** saat handoff ditulis — proses batch p1 (task
  background sesi lama) kemungkinan MATI saat sesi ditutup → r10 bisa jadi run
  terpotong. Sesi baru WAJIB cek: `f-dev--django__django-11422--r10` punya
  verdict/swebench_eval? Terpotong → tandai invalid-infra (JANGAN redraw tanpa izin
  Mirza — STOP eksekusi berlaku).
- Working tree BERSIH, semua ter-commit. Container tersisa saat tulis: 11422-r10-a2.

## 5. Blocker

- Tidak ada blocker teknis. Kebijakan: **STOP peluncuran run baru** (keputusan Mirza) —
  termasuk antrean §-A0g (14855 pakai `--max-rerun` bila nanti diizinkan; 15902 nunggu
  R20; eksperimen falsifikasi 11910 nunggu izin).

## 6. Yang Akan Dikerjakan (AKAN) — urutan sesi baru

1. ~~Tutup papan validasi G2~~ **SUDAH DITUTUP di sesi lama** (semua 27 draw mendarat
   sebelum sesi berakhir): papan `artifacts/papan-skor-validasi-g2-mac.md` + §-A0h
   (`02c04ee`). Inti: kanari 15/15 hijau (nol regresi); 12184 rantai-N2 1/3 (r15 PASS
   bersih, turn ~3×); 11910/15388 0/3 (dinding = agenda G3); 11422 0/3 (flaky, pooled
   2/8). N1 menembak 2× (11910 r12, 11422 r10).
   **+ SWEEP FREKUENSI REPETISI juga sudah dilakukan** (katalog `649ac60`): ~22% reply
   korpus = repetisi; **periode-2 & intra-reply MEMENUHI syarat naik** (spesimen penentu
   12184 r14: periode-2 di FIX pasca-G2, ~29 turn lolos dari N1) + kelas-4 baru
   "near-duplicate full-file rewrite" (13230 r4, catat-only). **Keputusan promosi
   kedua kandidat = agenda diskusi Mirza di sesi baru** (bersama R14+N3).
2. **R15** (LV-14 detektor dua-arah region-hunk, eval-realm label-only) via subagent —
   sudah disetujui Mirza; baca katalog LV-14 dulu.
3. **Diskusi draft desain R14+N3** (oracle repro) dgn Mirza — bukti-kasus utama 12184
   r13; pertanyaan kunci: batas mekanis-vs-prompt (CONTROL-MARKER opt-in), polarity
   lint, body-assert. JANGAN koding sebelum desain disepakati.
4. **Desain R17/LV-13a** setelah #3 — cek peluang berbagi primitif "verifikasi
   klaim-ke-kode" dgn N2 (menjangkau varian-2/3 cacat evidence).
5. Ide yang sudah dilempar ke Mirza, belum diputus: "regression sniff" gold-blind
   (gate jalankan test file modul yang disentuh patch) sebagai alternatif
   gate-subset-P2P.

## 7. Referensi

| Referensi | Kapan dibaca |
|---|---|
| `docs/urutan-retest-lever.md` §-A0f/§-A0g | Di awal — hasil rate G1 + antrean beku |
| `docs/rekomendasi-lever-dari-taksonomi.md` §7 | Di awal — lineup G2-baru & yang ditunda |
| `docs/katalog-lever.md` (ekor, entri claude-mac 22-07) | Sebelum diskusi desain — semua spesimen & kandidat catat-only |
| `docs/koreksi-hipotesis.md` KH-20/21/22 | Sebelum baca papan apa pun |
| `artifacts/papan-skor-rate-origin-r1-mac-g1.md` | Baseline pembanding papan G2 |
| `scripts/run_rlfv_batch.py --help` | Sebelum run apa pun (--parallel, --max-rerun) |

## 8. Keputusan User (Mirza) sesi ini

| Keputusan | Isi |
|---|---|
| Paralelisme | 2-3 → 5 → **maks 7** (endpoint eksklusif; rolling pool) — tersimpan di memory |
| Protokol | Top-up n=5 pooled lintas-rezim; kanari stabil same-session n=3 |
| G2-baru | N1+N4+R12+N2; R9/R8/R10→G3; N3→R14 |
| Cakupan putaran akhir | HANYA lever label/orkestrasi (1+2); periode-2 & dedup intra-reply DITUNDA (anti-overfit; syarat naik tercatat di katalog) |
| Eksekusi | **STOP run baru**; lookup case lain dari artefak / lanjut G3 |
| Sesi baru | Handoff → R15 subagent → diskusi desain R14+N3 → R17/LV-13a setelahnya |

## 9. Anti-Patterns / Lessons (CARRY FORWARD + baru)

- ❌ **Lid-close Mac = pembunuh run** (2 korban: 12184 r11, 15388 r9): koneksi half-open,
  driver hang tanpa timeout (kini R12/infra-abort memutus, tapi tetap hindari). caffeinate
  TIDAK menahan clamshell sleep. Solusi nyata: lid terbuka atau `sudo pmset -a disablesleep 1`.
- ❌ **Sesi paralel lain di repo ini men-checkout/menyapu working tree** (2 insiden) —
  commit SEGERA setelah setiap unit kerja selesai; jangan biarkan edit menginap.
- ❌ Test yang MEMOCK emit tidak memvalidasi whitelist event/verdict sungguhan (insiden
  `evidence-audit` crash runtime) — selalu ada ≥1 test tanpa mock utk nama event/label baru.
- ❌ `_mk_run` helper test tabrakan nama (definisi belakangan menang senyap) — cek nama
  helper sebelum append ke file test besar.
- ❌ zsh: `===` di command = glob error; `$c:latest` = jebakan modifier — quote semuanya.
- ⚠ `qualified_rerun` memilih rerun qualified TERTINGGI — L segar yang qualified otomatis
  jadi input FIX berikutnya (dipakai sadar utk rantai-N2 12184 l-r3; jangan kaget input
  beku "berpindah" setelah run L baru).
- ✅ Pola task background: proses batch mati bersama sesi — draw in-flight saat sesi tutup
  = kandidat run terpotong, cek verdict-nya di sesi baru.

## 10. Catatan Lain

- **Rezim run G2:** `mac-arm64-rosetta | kode s.d. 9777148 | G1+G2(N1,N4,R12,N2) aktif |
  lane allow-concurrent/parallel` — draw 12184 r13-r15 SAJA yang memakai L ber-audit-N2
  (l-r3); origin lain L beku lama (isolasi efek FIX-lever).
- Image di Mac: 4 origin + 15790 + 13230 + 11049 + 15347 + astropy-6938 + 14855. Disk aman.
- Memory harness: `gemma-endpoint-parallel-lanes.md` (7 lane + --parallel).
- 6 laporan subagent lengkap ada di transcript sesi lama; intinya SUDAH dikatalogkan —
  jangan re-derive, baca katalog/KH.
- MCP agent-bus MATI di mesin ini; file handoff ini = satu-satunya estafet.
