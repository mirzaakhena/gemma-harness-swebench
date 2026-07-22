# RLFV Grup-1+2 — Papan Skor & Cases untuk Re-test (koleksi durable lintas-sesi)

**Dibuat:** 2026-07-21 (bot-02, sesi `task-rlfv-untouched-41-g1`).
**Tujuan:** koleksi PERSIST lintas-sesi (permintaan Mirza) — papan skor grup-1+2 +
daftar case menarik untuk **re-test SETELAH 103 tuntas**. Sesi/bot baru baca ini
supaya tak kehilangan konteks.
**Terkait:** [[katalog-lever]] (autopsi grup-1+2, commit `d453bc7`),
[[sop-rlfv-case-run]], [[koreksi-hipotesis]], [[taksonomi-kegagalan-per-fase]],
[[urutan-retest-lever]], [[audit-integritas-cases-selesai]], Plane **SMARTXRESE-391**
("Retest ulang seluruh 103 cases"). Aturan main: **catat, jangan terapkan lever**
tanpa instruksi Mirza; papan skor end-to-end HARUS hitung wrong-file/skip sebagai gagal.

---

## 1. State saat ini (per 2026-07-21)

- **41 belum-tersentuh** = grup-1 (10) + grup-2 (10) + grup-3 (10) + grup-4 (11).
  - **Grup-1 & 2 dijalankan** (17/20 selesai). **Grup-3 & 4 BELUM di-setup/jalan.**
- **Belum selesai di grup-1/2:** `11564` (reproduce-wall KH-10, belum tuntas),
  `12113` (belum jalan), `13925` (DIHAPUS dari f-dev — wrong-file, atas perintah Mirza).
- **Keputusan eksekusi Mirza:** **serial ke depan** (paralel net-negatif — §4). **max-2
  concurrent akan DITES** sebelum diadopsi (hipotesis: 2-lane isi idle-GPU saat lane lain
  di step CPU/gate). Baseline serial bersih tersedia.
- **Flag baru batch runner** (`scripts/run_rlfv_batch.py`):
  - `--prune-localize-miss` (orkestrasi, BUKAN gate produk): skip FIX bila l-dev
    `gold_eval.file_match=false` → `error=skipped-fix-localize-miss` (tetap dihitung gagal).
    **Pakai ini di run serial ke depan.**
  - `--allow-concurrent` (EKSPERIMEN): bypass gate GPU penuh. **Jangan** dipakai serial.

## 2. Papan skor pembeda grup-1+2 (17 case selesai) — SOP §4

Angka mentah resolved=3/17 MENYESATKAN. Pembedaan:

- **🟢 Hijau kandidat-asli (2):** `12908`, `12983` — `file_match`✓ `line_overlap`✓.
  (§3b patch-vs-gold BELUM dijalankan — deferred.)
- **⚠️ resolved=true + file_match=FALSE (1):** `11620` — model patch `django/urls/resolvers.py`;
  gold `django/views/debug.py`. F2P `test_technical_404_converter_raise_404` lolos + **66 P2P
  lolos, 0 regresi**. **Instans ke-2 pola pasca 13658.** BELUM dipastikan lulus-palsu-sejati
  vs **fix-alternatif-lokasi-valid** — 0-regresi condong ke "valid di file lain". Butuh **§3b
  sabotase** untuk pastikan.
- **🔴 Merah — localize benar, patch salah (5):** `13551`, `15819`, `astropy-14182`, `11019`,
  `11283` (`file_match`✓, F2P gagal). Autopsi §3 per-case DEFERRED (akar-MODEL FIX vs repro-longgar?).
- **🔴 Merah — salah-file / akar-LOCALIZE (1):** `11742` (`file_match`=false). **Kelas-A**
  (bareng `13925`, `11797`, `13158`). Frekuensi Kelas-A grup ini: 2/17.
- **🧱 REPRODUCE-wall, tak sampai FIX (6):** `14411`, `14608`, `12184`, `13265`, `13321`, `11630`.
  Sub-signature terkonfirmasi: `14411` = **KH-12 no-fence** (`<|tool_call>` tanpa fence, 0-exec,
  40 turn ×3); `11564` = **KH-10 Python 3.6** (`subprocess.run(text=...)` TypeError berulang,
  exec JALAN tapi crash API-version). **REPRODUCE-wall = mode kegagalan DOMINAN** case
  belum-tersentuh (≥6/17) — konsisten peringatan handoff bot-04 (regresi-territory, RLFV > baseline).
- **❓ Reached-FIX-no-VERIFY (2):** `12470`, `15388` — verdict FIX ADA, `swebench_eval.json`
  TIDAK (resolved=None), spec ADA (bukan "spec hilang"). Perlu autopsi kenapa checker tak
  hasilkan eval — DEFERRED.

## 3. Cases untuk RE-TEST setelah 103 tuntas (curated — arahan Mirza)

| Case | Kenapa menarik | Check yang harus dijalankan |
|---|---|---|
| `11620` | resolved=true + file_match=false, 0 regresi | **§3b sabotase**: lulus-palsu-sejati vs fix-alternatif-valid? Baca test + banding patch model (`urls/resolvers.py`) vs gold (`views/debug.py`) |
| `12908`, `12983` | hijau, belum dikonfirmasi | **§3b** patch-vs-gold semantik (setara/lebih-sempit/longgar?) |
| `13925`, `11742` | Kelas-A salah-file | Konfirmasi akar-LOCALIZE (gold tak masuk kandidat); kandidat opsi-2 cross-check localize-vs-repro |
| `13551`,`15819`,`astropy-14182`,`11019`,`11283` | merah, localize benar | §3 per-case: akar-MODEL-FIX vs repro-longgar (LV-01/K4)? Buka `fix.diff` + f2p/p2p |
| `14411` | KH-12 no-fence | Target lever no-progress breaker (watcher ≥3 identik → putus-dini + inject) |
| `11564` | KH-10 Python 3.6 | Sama; + kandidat feedback-injection antar-rerun (lihat §4) |
| `12470`, `15388` | reached-FIX-no-VERIFY | Kenapa checker tak hasilkan `swebench_eval`? (spec ada) |

## 4. Temuan sesi ini (detail di [[katalog-lever]])

- **Throughput paralel NET-NEGATIF di GPU shared saturated.** Serial per-case 2.8–25.9 mnt;
  3-lane concurrent 18–**98** mnt (rerun-berat 4-6× lebih lambat). GPU owner `derry-gemma4-31b-dp`
  100% util → vLLM batching tak untung (bagi-bagi compute). **Serial menang.** Bukan "tak mampu
  paralel". Max-2 = hipotesis belum-teruji.
- **Kandidat lever (BELUM DITERAPKAN):**
  1. **No-progress breaker** (keputusan Mirza: putus-dini + watcher inject peringatan mekanis saat
     ≥K reply identik). Reminder murni tak cukup (14855/15902).
  2. **Rerun-diversity** (keputusan Mirza: **(b) feedback-injection deterministik**, BUKAN
     seeded-temperature — utamakan reproducibility). Rerun byte-identik di temp-0 = budget sia-sia.
  3. **Graceful-shutdown**: signal handler tulis verdict `interrupted` saat run di-kill (nutup akar
     false-live/stale di sisi-tulis; komplementer fix dashboard mtime `9476fc6`).
  4. **Cegah wrong-file lolos FIX (1+2)**: (1) prune orkestrasi = **SUDAH DITERAPKAN** (`--prune-localize-miss`,
     commit `de43a91`); (2) gate LOCALIZE blind cross-check localize-vs-repro-touched-files = **KANDIDAT**
     (harness, tunggu instruksi). DILARANG cek-gold di gate produk (gold-blind).
- **Dashboard** (semua DITERAPKAN sesi ini): radio filter All/PASS/FAIL, modal info/reason,
  kolom "mulai" dipindah, tombol copy-JSON per case (`{"case","phase","run"}`), label `(stale?)`
  vs `(live)`, `--host` untuk akses LAN. Viewer: `python ui/server.py --root ..\artifacts --port 8766 --host 0.0.0.0`.

## 5. Pekerjaan NEXT (urutan)

1. **Tuntasin 103** (prioritas Mirza): setup + run **grup-3** (`14155,14534,15061,15213,15252,15781,12284,12589,12856,13033`) &
   **grup-4** (`13315,13448,13757,13933,13964,14730,14997,14999,15202,15695,15738`) — **serial + `--prune-localize-miss`**.
   Plus tuntasin `11564`, `12113` (grup-2 sisa). Catatan: `15388`(grup2) & `15388`-area historis infra-GPU-fail;
   `astropy-*` butuh `PYTHONUTF8=1`.
2. **Tes max-2 concurrent vs serial** (matched cases, ukur wall-clock) → adopt kalau menang.
3. **Re-test cases menarik** (§3) setelah 103 tuntas.
4. Autopsi per-case merah + §3b 11620 + investigasi 12470/15388.
5. Per milestone: autopsi → katalog → commit (SOP §5-§7). Lapor Mirza papan skor pembeda (bukan agregat).

## 6. Artefak & anchor

- HEAD sesi bot-02 berakhir di sekitar commit `d453bc7` (autopsi) — lihat `git log`.
- State batch: `..\artifacts\{batch-bot02-g1,g2-lane1,g2-lane2,g2-lane3,g2-lane3b}.json`.
- Endpoint Gemma: `http://10.8.0.86:8000/v1`, model `google/gemma-4-31B-it`.
  gpu_check: `python C:\Users\Mirza\workspace-shared\smartm2m-bench\swe\harness-uplift\swebench-original\gpu_check.py`.
- Trailer commit `Agent: <bot>` wajib. Commit data case baru (`cases/problems`, `cases/gold`) juga.
