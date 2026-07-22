# Pindah Mesin Sementara ke macOS — setup lengkap + siap re-run origin R1 (gating G2)

**Date:** 2026-07-22 18:58 (WIB)
**Repo kerja:** /Users/mirza/Workspace/gemma-harness-swebench/main (macOS, arm64)
**Branch:** main (HEAD: ed118c1)
**Dari → Ke:** claude-mac (sesi tunggal di Mac) → sesi berikutnya (Mac ini, ATAU bot Windows saat jaringan kantor pulih)
**Pair:** —
**Lanjutan dari:** `.handoff/202607211420-prompt-rlfv-finish-103-serial.md` (bot-02→bot-03) + rantai §-A0 di [[urutan-retest-lever]]
**Plan terkait:** Plane SMARTXRESE-391 (retest 103); gating G2 per §-A0e

---

## 1. Tujuan Handoff

**Konteks pindah:** jaringan internet kantor bermasalah → kerja pindah sementara dari PC Windows (rumah armada bot-01..06) ke Mac ini. Armada bot TIDAK ada di sini — hanya satu sesi Claude ("claude-mac"); semua peran (strategi/lever/retest) dipegang satu sesi. Sesi ini menyiapkan mesin Mac sampai siap menjalankan pipeline penuh. **Goal berikutnya: re-run 4 origin R1 n=3 (gating G2, keputusan Mirza §-A0e).**

## 2. Konteks Proyek

Harness SWE-bench utk Gemma, pipeline per-fase REPRODUCE→LOCALIZE→FIX→VERIFY, product harness gold-blind total, eval vs gold di `eval/`. Status program: board 103 first-pass tuntas (40/103 resolved, kompas bukan skor); **Gelombang-1 (9 lever) TERPASANG**; protokol resolve-rate k/n (n≥3) DIADOPSI utk FIX (KH-20: FIX stokastik; REPRODUCE-wall boleh single-run); **G2 DI-GATE** menunggu resolve-rate riil 4 origin R1. Peta lengkap: [[urutan-retest-lever]] §-A0..§-A0e.

## 3. Yang Sudah Selesai (SUDAH) — sesi ini

- **Vault Obsidian docs/ ter-link penuh** (`cfcffde`): 103 wikilink lintas 16 dokumen + blok "Terkait" ber-anotasi; 0 broken; `docs/.obsidian/` di-gitignore. Nama artefak run (repro.md dkk.) & rujukan luar-vault sengaja tak disentuh.
- **`scripts/gpu_check.py` DIREKONSTRUKSI lintas-platform** (`8ac903f`) — skrip Windows lama (`C:\...\swebench-original\gpu_check.py`) tidak ikut ke Mac. Sumber: `:8000/metrics` vLLM (running/waiting, dijumlah lintas 2 engine DP — penentu vonis, fail-loud) + `:8409/api/stats` GPU 0–3 (informatif). **Kontrak output sama**: baris terakhir `vLLM queue: {'running': N, 'waiting': M}` → `parse_waiting()` batch runner & SOP §1a utuh. `GPU_CHECK` di `run_rlfv_batch.py` → `scripts/gpu_check.py`. TDD: `tests/test_gpu_check.py` 6 test.
- **swebench==4.1.0 + datasets==4.8.5 terinstall** di Python 3.12 sistem → **suite penuh 474 hijau** (test_swebench_checker/compat yang tadinya gagal-environment ikut hijau).
- **Docker siap**: 4 image Epoch origin R1 pulled — `django__django-11422/-11910/-15388/-12184` (~8,6 GB; disk sisa 249 GB). **Smoke test lolos**: container x86_64 jalan via Rosetta, `/opt/miniconda3/envs/testbed/bin/python` → Python 3.6.13, exit 0.
- **Konektivitas diverifikasi dari Mac**: endpoint Gemma `http://10.8.0.86:8000/v1` (model `google/gemma-4-31B-it`, max_model_len 262144, vLLM 2-engine DP) + stats `http://10.8.0.86:8409/api/stats` (host H100accio, 4× H100 80GB, owner `derry-gemma4-31b-dp`) — keduanya terjangkau.

## 4. Yang Sedang Dikerjakan (SEDANG)

— Berhenti di titik bersih. Working tree clean, nol container, GPU idle (waiting=0 saat terakhir dicek), tak ada batch berjalan. (HEAD `ed118c1` = commit spec API JSON UI viewer dari sesi paralel lain di mesin ini — bukan sesi penulis handoff.)

## 5. Blocker

- **Jaringan kantor** (sebab pindah) — armada bot Windows & artefak historis `..\artifacts` di PC Windows TIDAK terjangkau dari sini. Artifacts run lama tak tersedia utk autopsi sampai kembali/tersinkron.
- `..\artifacts` di Mac ini kemungkinan KOSONG/baru — run baru akan mulai menulis di sini → **dua pohon artifacts terpisah** (Mac vs Windows) yang kelak perlu rekonsiliasi. Jangan asumsikan runs.jsonl historis ada.

## 6. Yang Akan Dikerjakan (AKAN)

**Goal (gating G2, urutan §-A0e):** re-run 4 origin R1 — `11422`, `11910`, `15388`, `12184` — **n=3 per case, SERIAL + `--prune-localize-miss`**, hitung resolve-rate k/n → autopsi → BARU brief G2.
- Opsional (arahan §-A0e butir 4): naikkan kanari goyang `13230`/`15790` ke n=3 utk baseline rate kanari (butuh pull image dulu).
- Setiap run **WAJIB berlabel rezim BARU** (lihat §10 — rezim-mac beda dari rezim-Windows).
- Setelah batch: autopsi per SOP §3/§5 → katalog → commit → lapor Mirza papan skor rate-based (k/n, bukan biner).
**Starting point:** baca [[urutan-retest-lever]] §-A0c/§-A0d/§-A0e DULU, lalu [[sop-rlfv-case-run]] §1 (GPU/serial).

## 7. Referensi

| Referensi | Kapan dibaca |
|---|---|
| `docs/urutan-retest-lever.md` | **Di awal** — §-A0e keputusan gating; §-A0d protokol rate; §2 urutan |
| `docs/sop-rlfv-case-run.md` | **Di awal** — §1a GPU serial (gpu_check baru tetap kompatibel), §3 protokol, §9 anti-pattern |
| `docs/rekomendasi-lever-dari-taksonomi.md` | Konteks G1 terpasang (hash commit per lever) + G2/G3 catat-only |
| `docs/koreksi-hipotesis.md` | KH-20 (FIX stokastik — dasar protokol rate) sebelum baca papan skor apa pun |
| `docs/taksonomi-kegagalan-per-fase.md` | Saat klasifikasi hasil run baru |
| `scripts/gpu_check.py` | Sebelum run Gemma pertama — baca docstring kontrak output |

## 8. Keputusan User Lewat Brainstorming (sesi ini)

| Pertanyaan | Pilihan Mirza | Konsekuensi |
|---|---|---|
| Cakupan linking vault | Konversi + blok Terkait | (terpasang `cfcffde`) |
| Wikilink di entri append-only | Boleh inline (format ≠ substansi) | entri beku katalog/koreksi tetap utuh isinya |
| Install swebench + docker + commit | Ya, semua | mesin siap pipeline penuh |
| Trailer commit di Mac | `Agent: claude-mac` | armada bot-xx hanya eksis di PC Windows |

## 9. Anti-Patterns / Lessons (CARRY FORWARD + baru sesi ini)

- ❌ **zsh: `$c:latest` = jebakan** — zsh membaca `:l` sebagai modifier lowercase → URL image rusak (`...11422atest`). Selalu `${c}:latest`. Sudah memakan 1 ronde pull gagal.
- ❌ JANGAN bandingkan wall-clock run Mac dengan run Windows historis — **emulasi Rosetta** (image x86_64 di arm64) melambatkan container; label rezim wajib beda (§0.4).
- ❌ JANGAN percaya label verdict; ❌ JANGAN cek-gold di gate produk; ❌ JANGAN paralel tanpa aba-aba — semua carry-forward dari handoff sebelumnya, masih berlaku.
- ✅ gpu_check baru **fail-loud**: metrics tak terjangkau → TIDAK ada baris queue (waiting=None) → batch runner menunggu, bukan lolos palsu. Jangan "perbaiki" jadi default-0.
- ✅ Path Windows di docs (gpu_check lama, `main\`, PowerShell) = jejak historis; di Mac semua sudah POSIX + `scripts/gpu_check.py`.

## 10. Catatan Lain

- **Rezim mesin ini (utk label papan skor):** `mac-arm64-rosetta | harness ed118c1 | G1 aktif | swebench 4.1.0 | py3.12` — BUKAN comparable dgn rezim run historis Windows.
- Python: 3.12 (framework build, sistem). Docker 28.4.0, daemon jalan. Image baru 4 origin R1 saja — case lain perlu `docker pull` dulu (`ghcr.io/epoch-research/swe-bench.eval.x86_64.<case>:latest`; ingat jebakan zsh).
- Vault Obsidian = `docs/` (bukan mirza-vault Windows). Plugin obsidian@obsidian-skills terpasang di Claude Code (marketplace kepano/obsidian-skills).
- Rujukan vault Windows (`C:\Users\Mirza\mirza-vault\...`) di docs TIDAK terjangkau dari Mac.
- Commit sesi ini: `cfcffde` (linking docs) + `8ac903f` (gpu_check). Trailer `Agent: claude-mac`.
- MCP agent-bus/pty-controller (antar-bot) MATI di mesin ini — jangan coba kirim handoff via agent-bus; file ini = satu-satunya jalur estafet.
