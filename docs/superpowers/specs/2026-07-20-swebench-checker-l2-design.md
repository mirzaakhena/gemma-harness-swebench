# Spec Desain — SWE-bench Checker (L2) + Dashboard Status 2-Lapisan

Status: DISETUJUI Mirza (brainstorm Telegram 2026-07-20, sesi bot-05; semua
butir dikunci via button/pesan eksplisit). Sumber keputusan: vault "Desain
SWE-bench Checker L2 — Keputusan Brainstorm" + README §"Aturan status
2-lapisan" + kontrak-output.md + prinsip-pengembangan.md. Dokumen bahasa
Indonesia; semua teks yang dilihat model = English (tidak relevan di sini —
checker tidak pernah bicara dengan model).

## 1. Tujuan & definisi

Membangun **checker SWE-bench asli** sebagai modul eval realm-development
yang menghasilkan vonis `resolved` (bahan `pass_l2`), lalu menerapkan
**aturan status 2-lapisan** di dashboard.

Dua lapisan penilaian atas `fix.diff` yang SAMA:

| Lapisan | Juri | Pertanyaan yang dijawab | Field |
|---|---|---|---|
| L1 — product (gold-blind) | `repro.py` beku fase R, gate `run_fix_gates` | gejala spesifik issue hilang? | `pass_l1` di `verdict.json` |
| L2 — development (checker ini) | test resmi maintainer via grading resmi SWE-bench | resolved TANPA regresi? (F2P + P2P) | `resolved` di `swebench_eval.json` |

L2 menangkap yang L1 buta: patch special-casing repro, fix salah arah, dan
**regresi** (P2P — `repro.py` tak pernah mengecek fitur lain).

## 2. Posisi arsitektur (keputusan terkunci)

- **SATU modul** (SRP): `eval/swebench_checker.py`, hidup di realm dev
  (`eval/`). Dipanggil manual/dev-eval FIX sekarang; stage VERIFY nanti
  jadi **caller tipis** modul yang sama. TIDAK ditanam di driver/gate FIX.
- **Vonis pakai grading resmi**: paket `swebench` v4.1.0 (terpasang;
  `swebench.harness.grading.get_eval_report`) — BUKAN tulis parser sendiri,
  BUKAN menjalankan runner `inspect_evals` (overkill: ikut generation).
  Hasil verifikasi 2026-07-20: di `swebench-original/` TIDAK ada checker
  lokal reusable (klaim handoff sebelumnya keliru); engine k-run
  `swe_dyn`/`verifier` hanya Go/Rust (preseden pola, bukan kode pakai).
- **Boundary integritas** (sama dengan `fix_gold_eval`): checker jalan
  SETELAH run selesai; hasil TIDAK pernah diumpankan ke loop Gemma;
  `verdict.json` / `events.jsonl` TIDAK pernah disentuh (append-only,
  ditulis-sekali). `pass_l2` di `verdict.json` tetap `null` di kampanye
  f-dev — field itu baru diisi product saat stage VERIFY lahir.
- Windows: import `swebench` butuh **shim modul `resource`** (Unix-only) —
  sudah diverifikasi jalan; shim jadi bagian modul checker.

## 3. Data beku per case — `swebench_spec.json`

`test_patch` / `FAIL_TO_PASS` / `PASS_TO_PASS` belum ada di repo; sumber
resmi = dataset HF `princeton-nlp/SWE-bench_Lite` (cache lokal ada di
`~/.cache/huggingface/datasets`). Keputusan: **freeze sekali fetch**.

- Skrip `eval/fetch_swebench_spec.py` (sekali jalan per case, dev tooling):
  baca row dataset per `instance_id` → tulis
  `cases/gold/<case_id>/swebench_spec.json`.
- Isi minimal: `instance_id`, `repo`, `version`, `base_commit`,
  `test_patch`, `FAIL_TO_PASS` (list), `PASS_TO_PASS` (list), plus
  `dataset` + `fetched_at` (provenance).
- Checker HANYA membaca file beku ini (offline, reproducible, ke-review di
  git). Case tanpa spec → error jelas menyuruh fetch dulu.

## 4. Modul checker — alur & pemisahan lapisan

Pola pemisahan mengikuti FIX (`fix_gates` pure vs `fix_patch_runner`
docker):

- **Fungsi pure** (teruji tanpa docker): komposisi skrip eval, pemetaan
  hasil `get_eval_report` → struktur `swebench_eval.json`, klasifikasi
  daftar test lulus/gagal.
- **Lapisan docker**: container Epoch segar
  (`ghcr.io/epoch-research/swe-bench.eval.x86_64.<case_id>:latest` — image
  yang SAMA dengan gate FIX, sudah ada lokal utk case aktif); pola mount
  `repro_sandbox_runner`/`fix_patch_runner` (`/patch-in` read-only, conda
  env `testbed`).

Alur satu invokasi:

1. Baca `files/fix.diff` run dir + `swebench_spec.json` case itu.
2. Container segar: apply `fix.diff` (patch model) → apply `test_patch`
   resmi → jalankan test F2P ∪ P2P dengan test-command per-repo pola resmi
   SWE-bench → tangkap output mentah.
3. Output mentah disimpan `files/swebench_test_output.log` (append-only ke
   run dir files/, telemetri-sejak-hari-pertama).
4. Host: parse log via `swebench.harness.grading` (log parser per-repo
   resmi) → `resolved` + rincian per-test.
5. Tulis `swebench_eval.json` di run dir + echo JSON ke stdout (pola
   `gold_eval.json`). UTF-8 tanpa BOM, LF.

CLI (pola eval/ seragam):

```
python -m eval.swebench_checker --case <case_id> --rerun <N>
    [--campaign f-dev] [--artifacts ../artifacts] [--image <override>]
```

## 5. Skema `swebench_eval.json` (KAYA — mandat log-trace Mirza)

```json
{"case": "...", "rerun": 1, "resolved": true,
 "f2p_passed": ["..."], "f2p_failed": [],
 "p2p_passed_count": 123, "p2p_failed": [],
 "image": "ghcr.io/epoch-research/...", "spec": "cases/gold/.../swebench_spec.json",
 "log": "files/swebench_test_output.log", "checked_at": "..."}
```

- `f2p_failed` tidak kosong → fix belum tuntas (test mana yang masih gagal).
- `p2p_failed` tidak kosong → **regresi yang disebabkan patch**, per nama
  test — bahan evaluasi balik ke fase R/L.
- `resolved` = definisi resmi: semua F2P lulus DAN semua P2P tetap lulus.
- P2P lulus cukup count (daftarnya bisa ratusan); yang gagal selalu
  eksplisit per nama.

## 6. Dashboard status 2-lapisan (`ui/server.py`)

**Disambiguasi nama (penting — sempat tertukar di brainstorm, diluruskan
Mirza msg 2297-2298):** ada DUA file eval berbeda di run dir.
`swebench_eval.json` = hasil SWE-bench checker (menjalankan test resmi) —
**INILAH penentu PASS**. `gold_eval.json` = hasil `fix_gold_eval`
(pembanding alamat file/baris, tanpa eksekusi) — advisory murni; dia tak
membuktikan fix bekerja, dan fix alternatif yang benar di file berbeda
akan salah divonis olehnya. Label di dashboard wajib membedakan keduanya
secara eksplisit (mis. "VERIFY (SWE-bench)" vs "gold-match (advisory)").

- **Tab FIX di-rename "FIX and VERIFY"** (keputusan Mirza): dashboard =
  alat monitoring development, checker ini secara tak langsung pekerjaan
  VERIFY. TIDAK ada tab keempat. **Struktur/tampilan tab TETAP seperti
  sebelumnya** — hanya label yang berubah (keputusan Mirza msg 2297).
- `case_status()` dibenahi — menutup known issue flip→FAIL (verdict `flip`
  tak dikenal, jatuh ke default FAIL, inkonsisten dengan `verdict_icon`).
- Status per run kampanye `f-*` (merge saat render, viewer tetap
  read-only — pola `merge_gold_verdict`):

| Kondisi | Status |
|---|---|
| `pass_l1` ✅ ∧ `swebench_eval.resolved` ✅ | **PASS** |
| product FAIL (no-flip/timeout/abort/…) tanpa sinyal L2 | **FAIL** (alasan product) |
| `pass_l1` ✅ ∧ `resolved` ❌ | **FAIL** (alasan: daftar `f2p_failed`/`p2p_failed`) |
| `pass_l1` ✅ ∧ `swebench_eval.json` belum ada | ⏳ **"product-pass, menunggu VERIFY"** — state ketiga, BUKAN FAIL |
| product FAIL ∧ `resolved` ✅ | ⚠️ **ANOMALY** (keputusan Mirza msg 2297): repro bilang gejala masih ada tapi test resmi bilang resolved — kontradiksi sinyal, di-flag menonjol utk autopsi, BUKAN diam-diam FAIL |

- `gold_eval` (file/line match) tampil sebagai **advisory** (parameter
  penilaian tambahan, keputusan Mirza) — tidak menentukan PASS f-dev.
- **Detail per case di tab FIX and VERIFY** (keputusan Mirza msg 2297):
  bagian detail menjelaskan banyak hal secara mendetail — `pass_l1`
  (vonis repro product), `resolved` + daftar test F2P/P2P yang gagal
  (regresi per nama test), gold_eval advisory (file/baris vs gold), flag
  anomaly bila ada, dan tautan/lokasi log mentah
  `swebench_test_output.log`.
- Panel ringkasan ("pernah qualified") mengikuti definisi PASS baru.

## 7. `fix_gold_eval` — dipertahankan (keputusan Mirza)

Tetap jalan apa adanya: pembanding teks diff murni (<1 detik, tanpa
docker), sinyal "alamat" (file/baris terduga) — bahan evaluasi balik fase
REPRODUCE/LOCALIZE dan pendeteksi fix-alternatif (resolved=true tapi file ≠
gold = menarik dianalisa). Melengkapi checker (sinyal "fungsi"), bukan
digantikan.

## 8. Urutan kerja

1. **Probe manual** di run `f-dev--django__django-13660--r1`: jalur
   apply+test+grading dijalankan sekali secara kasar — memvalidasi asumsi
   API grading resmi (bentuk log parser, test-command django, format
   `get_eval_report`) SEBELUM modul final. Asumsi yang belum teruji
   end-to-end ditandai di sini, bukan disembunyikan.
2. Fetch + freeze `swebench_spec.json` utk 13 case populasi f-dev.
3. TDD modul checker (pure dulu, docker layer kemudian).
4. Dashboard 2-lapisan + rename tab + test.
5. Re-eval resmi run `13660--r1` → `swebench_eval.json` terisi →
   verifikasi tampilan dashboard (kasus uji nyata; dugaan: resolved=true,
   belum terbukti sampai checker jalan).

## 9. Testing (TDD wajib)

- Fungsi pure: fixture log test sintetis (django-style) → klasifikasi
  F2P/P2P + `resolved`; skema `swebench_eval.json`; komposisi skrip eval;
  error case (spec hilang, fix.diff hilang, apply gagal).
- Grading resmi di-mock/fixture di unit test — **nol docker & nol network
  di test suite** (pola test FIX: 46 test 0.24s).
- Test dashboard: `case_status` semua baris tabel §6 (PASS / FAIL product /
  FAIL L2 / menunggu VERIFY / flip dikenali).
- `python -m pytest` hijau dari root `main\` sebelum tiap commit.

## 10. Non-goals / batas diketahui

- Pipeline otomatis R→L→F→V level product: arah benar (konfirmasi Mirza),
  di luar scope spec ini.
- Bentuk stage VERIFY sebagai stage product: diputuskan nanti; spec ini
  hanya menjamin modulnya siap dipanggil caller tipis.
- Checker tidak dipanggil otomatis oleh driver/gate FIX (invokasi
  manual/dev — konsisten `fix_gold_eval`).
- Populasi di luar 13 case f-dev (Lite-300 dst): fetch spec-nya nanti saat
  ekspansi.
- Tidak ada perubahan schema kontrak-output (`swebench_eval.json` = file
  eval realm dev, bukan artefak kontrak; preseden `gold_eval.json`).
