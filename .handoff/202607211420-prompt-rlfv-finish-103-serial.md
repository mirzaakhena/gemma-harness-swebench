# RLFV — Tuntasin 103 (grup-3+4 + undone, serial+prune), Estafet bot-02 → bot-03

**Date:** 2026-07-21 14:20 (WIB)
**Repo kerja:** C:\Users\Mirza\workspace\gemma-harness-swebench\main
**Branch:** main (HEAD: 6dfafb7)
**Dari → Ke:** bot-02 → bot-03
**Pair:** —
**Lanjutan dari:** `.handoff/202607210855-prompt-rlfv-untouched-41-g1.md` (estafet bot-04→bot-02)
**Plan terkait:** Plane **SMARTXRESE-391** "Retest ulang seluruh 103 cases"; `docs/sop-rlfv-case-run.md`

---

## 1. Tujuan Handoff
Konteks bot-02 sudah sangat panjang (sesi maraton: 41-case grup-1+2 + banyak perbaikan dashboard + eksperimen paralel). **Goal estafet: tuntasin 103** — jalankan sisa case belum-tersentuh (grup-1/2 undone + grup-3 + grup-4) **serial + `--prune-localize-miss`**; case menarik di-re-test SETELAH 103 tuntas (arahan Mirza).

## 2. Konteks Proyek
Harness SWE-bench untuk Gemma, pipeline 4-fase per-fase-tuntas REPRODUCE→LOCALIZE→FIX→VERIFY. Product harness **gold-blind total**; eval vs gold di `eval/`. Prinsip: fisika > instruksi; `resolved=true` ≠ patch benar. Stack: Python stdlib + pytest, docker per case, endpoint Gemma vLLM, viewer 8766. Artifacts append-only di LUAR git tree (`..\artifacts`).

## 3. Yang Sudah Selesai (SUDAH)
- **Grup-1+2 (17/20) dijalankan**, papan skor pembeda + autopsi frekuensi → `docs/katalog-lever.md` (commit `d453bc7`). Ringkasan lengkap + cases-to-retest → **`docs/rlfv-papan-skor-grup12-dan-retest.md`** (`6dfafb7`).
- **Flag baru** `scripts/run_rlfv_batch.py`: `--prune-localize-miss` (`de43a91`, orkestrasi hemat-compute, BUKAN gate produk), `--allow-concurrent` (`f2cfa12`+`fa79c4b`, eksperimen).
- **Dashboard** (`ui/server.py`, semua DITERAPKAN + di-restart): radio filter, modal info/reason, kolom mulai dipindah, tombol copy-JSON per case, label `(stale?)` vs `(live)` (`9476fc6`), `--host` (`9bcb32c`). 128 test UI hijau.
- **Kandidat lever dicatat** (BELUM DITERAPKAN): no-progress breaker, rerun-diversity feedback-injection, graceful-shutdown, opsi-2 gate LOCALIZE cross-check. (Detail + keputusan Mirza di katalog + doc koleksi §4.)
- Plane SMARTXRESE-391 dibuat + komentar (41 tersisa, URL dashboard).

## 4. Yang Sedang Dikerjakan (SEDANG)
— Berhenti di titik bersih. Nol container gemma, GPU bebas, tak ada proses batch berjalan, tak ada commit tertunda. (Batch concurrent di-stop atas keputusan Mirza; 11564 mid-REPRODUCE di-kill → jadi run stale, itu OK, sudah ter-relabel.)

## 5. Blocker
—

## 6. Yang Akan Dikerjakan (AKAN)
**Goal:** tuntasin 103 (sisa 41-belum-tersentuh), SERIAL + `--prune-localize-miss`.
- **Undone grup-1/2:** `11564` (reproduce-wall KH-10), `12113` (belum jalan).
- **Grup-3 (10):** 14155, 14534, 15061, 15213, 15252, 15781, 12284, 12589, 12856, 13033.
- **Grup-4 (11):** 13315, 13448, 13757, 13933, 13964, 14730, 14997, 14999, 15202, 15695, 15738.
- Setup tiap case (`python -m scripts.prepare_cases --case ...` + `docker pull`), lalu `python scripts\run_rlfv_batch.py --cases <file> --state ..\artifacts\<state>.json --prune-localize-miss`. `astropy-*` → `PYTHONUTF8=1`.
- Autopsi §3+§5 per case → katalog → commit; lapor Mirza papan skor PEMBEDA (bukan agregat).
- Setelah run: **tes max-2 concurrent vs serial** (matched cases, ukur wall-clock) sebelum adopt.
**Starting point:** baca `docs/rlfv-papan-skor-grup12-dan-retest.md` DULU (§1 state, §5 next).

## 7. Referensi
| Referensi | Kapan dibaca |
|---|---|
| `docs/rlfv-papan-skor-grup12-dan-retest.md` | **Di awal** — state, papan skor, cases-to-retest, flag, keputusan |
| `docs/sop-rlfv-case-run.md` | **Di awal, SELURUHNYA** — prosedur, §3 protokol, §5 autopsi, anti-pattern |
| `docs/prinsip-pengembangan.md` | Di awal — arah Mirza, gold-blind, qualified |
| `docs/koreksi-hipotesis.md` | Di awal — KH-01..14 (klaim mati; KH-10 py3.6 & KH-12 no-fence relevan REPRODUCE-wall) |
| `docs/katalog-lever.md` | Saat autopsi — append-only, katalog JENUH → ukur frekuensi. Baca autopsi grup-1+2 di ekor |
| `README.md` | Peta repo + peringatan `resolved=true` |
| ~~`~/.claude/agent-playbook/PLAYBOOK.md`~~ | **SUDAH DIHAPUS dari disk** (cuma backup) — lewati |

## 8. Keputusan User Lewat Brainstorming
| Pertanyaan | Pilihan Mirza | Konsekuensi |
|---|---|---|
| Eksekusi ke depan | **Serial** (paralel net-negatif di GPU saturated) | Pakai run serial + `--prune-localize-miss` |
| max-2 concurrent | Adopt TAPI tes dulu vs serial | Ukur wall-clock matched sebelum pakai |
| Rerun-diversity | **(b) feedback-injection deterministik** | seeded-temperature DITOLAK (jaga reproducibility) |
| No-progress breaker | putus-dini + watcher inject peringatan | reminder murni tak cukup |
| Cegah wrong-file→FIX | 1+2; opsi-1 (prune) DITERAPKAN, opsi-2 (gate) kandidat | DILARANG cek-gold di gate produk |
| Stale runs | cukup relabel, jangan hapus fisik | fix dashboard mtime |
| Case menarik | re-test SETELAH 103 tuntas | prioritas = selesaikan board dulu |

## 9. Anti-Patterns / Lessons (CARRY FORWARD)
- ❌ **JANGAN paralel >1 tanpa aba-aba** — concurrency net-negatif di GPU shared saturated (serial per-case 3-26m vs 3-lane 18-98m). max-2 belum teruji.
- ❌ **Kill run = tinggalin stale** (no verdict → false-live). Kalau harus stop: stop container-nya juga; kill python ≠ kill docker container.
- ❌ **JANGAN cek-gold di gate produk** (run_localize_gates) — gold-blind sacred. Gold hanya di orkestrasi/eval DI LUAR loop model.
- ❌ **JANGAN percaya label verdict** (`syntax-fail`/`abort`) — buka artefak (`files/`, console.log, gold_eval file_match). resolved=true + file_match=false = flag (11620).
- ✅ **Verifikasi ke ARTEFAK** (ls run dir / gold_eval), bukan status agent. ✅ GPU serial: gpu_check `waiting==0`.
- ✅ **heredoc/Set-Content = mojibake** di Windows — pakai Write/Edit. Commit ber-tanda-kutip → `git commit -F file`.

## 10. Catatan Lain
- **HEAD `6dfafb7`.** Commit sesi bot-02 (banyak): setup g1/g2, dashboard×5, allow-concurrent+fix, prune, katalog (14411/breaker/temp-b/graceful/leak/papan-skor), server-host, koleksi doc.
- GPU bebas, nol container. Endpoint Gemma `http://10.8.0.86:8000/v1`, `google/gemma-4-31B-it`. gpu_check: `python C:\Users\Mirza\workspace-shared\smartm2m-bench\swe\harness-uplift\swebench-original\gpu_check.py`.
- Viewer 8766 sudah jalan (bind 0.0.0.0): akses LAN `http://192.168.18.17:8766/`, VPN `http://10.8.0.132:8766/`.
- **Lapor Mirza via Telegram** (chat_id `1121398977`): teach-me utk penjelasan, ringkas utk status, inline buttons tiap pertanyaan, immediate-reply sebelum tool call pertama, HINDARI tabel markdown. Log progress milestone bisa ke Plane SMARTXRESE-391.
- Trailer commit `Agent: bot-03` wajib. Commit data case baru (`cases/problems`, `cases/gold`).
- **`13925` sudah DIHAPUS** dari f-dev (wrong-file, perintah Mirza) — jangan bingung kalau f-dev = 61.
