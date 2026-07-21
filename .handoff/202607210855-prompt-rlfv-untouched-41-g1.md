# RLFV Full-Run 41 Case Belum-Tersentuh — Grup 1 (10 case), Estafet bot-04 → bot-02

**Date:** 2026-07-21 08:55 (WIB)
**Repo kerja:** C:\Users\Mirza\workspace\gemma-harness-swebench\main
**Branch:** main (HEAD: 946fe86)
**Dari → Ke:** bot-04 → bot-02
**Pair:** —
**Lanjutan dari:** —
**Plan terkait:** `docs/sop-rlfv-case-run.md` — SOP resmi, WAJIB dibaca seluruhnya sebelum kerja

---

## 1. Tujuan Handoff

Keputusan Mirza: jalankan **41 case yang belum pernah tersentuh RLFV** (Proyek B) lewat pipeline penuh. Dibagi **4 grup (10+10+10+11)**. **Giliranmu = GRUP 1 (10 case pertama)**; grup 2–4 ditentukan Mirza lagi setelah kamu selesai grup 1. Goal estafet: menutup corong 103 dengan menjalankan case-case yang belum pernah masuk pipeline kita.

## 2. Konteks Proyek

Harness SWE-bench untuk Gemma, pipeline **4 fase per-fase-tuntas**: REPRODUCE → LOCALIZE → FIX → VERIFY. Product harness **gold-blind total**; evaluasi vs gold hidup terpisah di `eval/`. Prinsip: **fisika > instruksi**. Stack: Python stdlib + pytest, docker per case, endpoint Gemma vLLM, viewer dashboard port 8766. Artifacts append-only di LUAR git tree (`..\artifacts`). Pelajaran termahal: **`resolved=true` = "tidak ada test resmi gagal", BUKAN "patch benar"**.

## 3. Yang Sudah Selesai (SUDAH)

- **bot-04 (sesi 2026-07-21):** 10 case A2 (Papan 103 baris 36-45) full R→L→F→V → **resolved 8/10** (commit range di HEAD `946fe86`); 13 case backlog jalur-1 → resolved 2/13; autopsi semua ke `docs/katalog-lever.md` + `docs/koreksi-hipotesis.md`. Fitur filter dashboard by-nama-case (`ui/server.py`). Tool baru `scripts/prepare_cases.py` (setup) + `scripts/relocalize_candn.py`.
- **Identifikasi 41 case belum-tersentuh:** vault `mirza-vault\Projects\SWE-bench Gemma Harness\RLFV vs Papan 103 — Regresi & Belum-Tersentuh.md` (cross-ref Papan 103 × artefak, 2026-07-21). Ke-41 belum punya SATUPUN run r/l/f-dev di Proyek B.

## 4. Yang Sedang Dikerjakan (SEDANG)

— (Berhenti di titik bersih. Nol container gemma-work/probe berjalan, GPU bebas, tak ada commit tertunda.)

## 5. Blocker

—

## 6. Yang Akan Dikerjakan (AKAN)

**Goal:** jalankan **10 case Grup 1** full R→L→F→V dari NOL (case belum ter-setup), autopsi tiap case, commit.

**Grup 1 (10 case, semua django):**
`12908, 12983, 13551, 14411, 14608, 11620, 12184, 12470, 13265, 13321`

**Langkah:**
1. **Setup** tiap case (belum ada problem/gold/spec/image): `python -m scripts.prepare_cases --case django__django-<id> ...` (fetch problem+gold+spec dari HF Lite) lalu `docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.django__django-<id>:latest`. Cek disk tiap beberapa pull (jangan tembus ~12GB); JANGAN hapus image milik proyek lain.
2. **Run RLFV** batch (jalan background, berjam-jam — tiap case R+L+F+V dari nol; REPRODUCE bisa 15+ mnt + s.d. 3 rerun): tulis 10 case ke file, `python scripts\run_rlfv_batch.py --cases <file> --state ..\artifacts\batch-bot02-g1.json`. Aman diulang (skip yang sudah punya `swebench_eval.json`). **Verifikasi ke ARTEFAK, bukan status agent** (anti-pattern §9).
3. **Per case: protokol pemeriksaan SOP §3** (lulus-palsu → patch-vs-gold semantik → kualitas repro a-d/K4 → sabotase bila mengubah kesimpulan) + **autopsi SOP §5** (1 subagent read-only per case, izin membantah; integrasi serial olehmu ke katalog) → **commit segera**.
4. **Lapor Mirza** papan skor yang membedakan hijau-asli/hijau-catatan/merah (bukan agregat mentah), per fase.

**Starting point:** branch `main` HEAD `946fe86`; baca `docs/sop-rlfv-case-run.md` SELURUHNYA dulu.

## 7. Referensi

| Referensi | Kapan dibaca |
|---|---|
| `~/.claude/agent-playbook/PLAYBOOK.md` | Di awal, sebelum kerja substantif |
| `docs/sop-rlfv-case-run.md` | **Di awal, SELURUHNYA.** Prosedur, protokol §3, disiplin epistemik §6, anti-pattern §9 |
| `docs/prinsip-pengembangan.md` | Di awal — arah Mirza, definisi qualified, aturan bahasa |
| `docs/koreksi-hipotesis.md` | Di awal — KH-01..KH-14 + addendum (klaim yang sudah dibantah; jangan ulangi) |
| `docs/katalog-lever.md` | Saat autopsi (§5). Append-only, bar tinggi, katalog JENUH → ukur frekuensi. Baca section batch A2 + backlog terbaru utk denominator (Tabel A=52) |
| `scripts/prepare_cases.py` / `scripts/run_rlfv_batch.py` | Sebelum setup / run — docstring jelaskan pola & jebakan |
| `README.md` | Peta repo + peringatan `resolved=true` |
| vault `RLFV vs Papan 103 — Regresi & Belum-Tersentuh.md` | Konteks: 41 belum-tersentuh + 13 regresi (kenapa case-case ini menarik) |

## 8. Keputusan User Lewat Brainstorming

| Pertanyaan | Pilihan Mirza | Konsekuensi |
|---|---|---|
| Cakupan | 41 case belum-tersentuh, dibagi 4 grup 10+10+10+11 | bot-02 grup-1 dulu; grup 2-4 Mirza tentukan setelah grup-1 selesai |
| Jalur eksekusi | **Full R→L→F→V dari nol** (bukan bypass) | case belum ter-setup → prepare_cases.py + full pipeline |
| Lever | catat, JANGAN terapkan | semua LV tetap BELUM DITERAPKAN |
| Setelah grup-1 | Lapor Mirza, tunggu keputusan grup berikutnya | JANGAN auto-lanjut grup 2 tanpa aba-aba |

## 9. Anti-Patterns / Lessons (CARRY FORWARD)

- ❌ **JANGAN taruh batch di background lalu akhiri turn.** Tunggu notifikasi + tindak lanjut; verifikasi ke ARTEFAK (ls run dir), bukan status agent. Timeout → ulangi.
- ❌ **JANGAN percaya label verdict** (`syntax-fail`/`wrong-logic` = bucket catch-all). Buka `files/`, `console.log`, `parse_actions` (KH-12).
- ❌ **JANGAN lapor hijau tanpa cek `file_match`** (recall detektor rendah). `line_overlap` bisa `null` — jangan bulatkan ke false.
- ❌ **JANGAN terapkan lever** / hapus image/volume proyek lain / timpa run dir lama.
- ❌ **JANGAN heredoc/Set-Content** di Windows (mojibake) — pakai Write/Edit. Commit message ber-tanda-kutip → tulis ke file, `git commit -F`.
- ✅ **GPU serial WAJIB** (`gpu_check` `waiting==0` + tak ada container `gemma-work-*` case lain sebelum tiap run Gemma). batch runner sudah handle. Dua run Gemma paralel = saling macet.
- ✅ **`swebench_spec.json` bisa HILANG** → `swebench_checker` exit-1 "spec not found" → resolved=None → nyangkut WAIT diam-diam di dashboard. Obat: `python -m eval.fetch_swebench_spec --case <id>`. (prepare_cases.py sudah fetch spec, jadi seharusnya lengkap.)
- ✅ **Dashboard viewer** baca daftar run dari `artifacts/<stage>/runs.jsonl` (index) + scan folder. Untuk hapus run dari dashboard = hapus folder DAN baris runs.jsonl (jarang perlu; jangan lakukan tanpa perintah Mirza).
- ✅ **astropy** (relevan grup 2+, `astropy-14182`): `swebench_checker` bisa crash `charmap` cp1252 di Windows → set `PYTHONUTF8=1`. Grup 1 semua django, aman.
- ✅ **Lapor Mirza via Telegram** (chat_id `1121398977`): teach-me utk penjelasan, ringkas utk status, inline buttons tiap pertanyaan, immediate-reply sebelum tool call pertama. HINDARI tabel markdown (auto-converter GFM gagal).

## 10. Catatan Lain

- **HEAD `946fe86`.** Commit sesi bot-04 hari ini: setup 10 A2 (`a63536e`), autopsi A2 (`12c0853`), spec-fix (`fix(cases)`), autopsi backlog (`4e18371`), UI filter (`6e52a3b`), record cand=N (`946fe86`). Tak ada remote → tak ada push.
- **Pembagian 4 grup (urutan dari listing Mirza):**
  - **Grup 1 (10):** 12908, 12983, 13551, 14411, 14608, 11620, 12184, 12470, 13265, 13321 ← GILIRANMU
  - Grup 2 (10): 13925, 15388, 15819, astropy-14182, 11019, 11283, 11564, 11630, 11742, 12113
  - Grup 3 (10): 14155, 14534, 15061, 15213, 15252, 15781, 12284, 12589, 12856, 13033
  - Grup 4 (11): 13315, 13448, 13757, 13933, 13964, 14730, 14997, 14999, 15202, 15695, 15738
  - Catatan: `15388` (grup 2) historisnya ⚠️ infra-GPU-fail di Papan 103 — bukan urusan grup 1.
- **Ekspektasi hasil grup 1:** campuran. Papan 103: 12908/12983/13551/14411/14608 = baseline✓ (regresi-territory kalau RLFV gagal); 11620/12184 = P23✅ Proyek A (bukan RLFV kita); 12470/13265/13321 = both-fail hard. Jadi jangan kaget kalau sebagian mentok REPRODUCE — itu datanya (lihat vault: RLFV regime lebih ketat).
- Endpoint Gemma: `http://10.8.0.86:8000/v1`, model `google/gemma-4-31B-it`. gpu_check: `python C:\Users\Mirza\workspace-shared\smartm2m-bench\swe\harness-uplift\swebench-original\gpu_check.py`.
- Viewer 8766 (opsional, buat pantau): `Start-Process -WindowStyle Hidden python -ArgumentList 'ui\server.py','--root','..\artifacts','--port','8766'` dari `main\`. Punya filter by-nama-case sekarang.
- **Trailer commit `Agent: bot-02` wajib.** Commit juga data case baru (`cases/problems`, `cases/gold`) — kalau tidak, setup hilang.
- **Setelah grup 1 selesai + di-commit:** lapor Mirza ringkasan, **JANGAN auto-lanjut grup 2** — tunggu aba-aba. Cek context sendiri (skill handoff §1); kalau ≥threshold, tawarkan handoff.
