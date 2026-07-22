# GEMMA-BASELINE: ablasi tanpa-harness pada 46 case yang harness MENANG — simple loop SWE-bench

**Date:** 2026-07-23 02:4x (WIB)
**Repo kerja BARU:** `/Users/mirza/Workspace/gemma-harness-swebench/gemma-baseline`
(buat dari nol — project terpisah dari `main/`)
**Referensi harness:** /Users/mirza/Workspace/gemma-harness-swebench/main (HEAD: 5afa68e)
**Dari → Ke:** claude-mac (sesi jaga-malam) → sesi BARU (Mac ini)
**Handoff saudara (task berbeda, jangan dicampur):**
`.handoff/202607230230-prompt-claude-play-referensi-57-case.md` (claude-play, 57 case GAGAL)
**Perintah asal (Mirza, verbatim intent):** listing semua case yang Gemma harness
BERHASIL → jalankan **Gemma baseline TANPA harness sama sekali** — simple loop yang
"bermain SWE-bench" — tetap **mematuhi aturan main SWE-bench**. Project baru di
`gemma-baseline/`.

---

## 1. Tujuan & kenapa ini berharga

Ini **eksperimen ABLASI (kontrol)**: PASS 46/103 saat ini dicapai Gemma DENGAN
harness RLFV penuh (gate, watcher, shortlist, oracle, rotasi kandidat, R20 parser,
dst). Pertanyaan yang dijawab baseline: **berapa dari 46 itu yang Gemma polos bisa
menangkan sendiri?**
- Baseline PASS suatu case → kemenangan harness di case itu BUKAN nilai-tambah
  harness (Gemma memang mampu).
- Baseline FAIL → selisihnya = **kontribusi kausal harness** — dan perbandingan
  log (baseline vs harness) di case yang sama menunjukkan MEKANISME mana yang
  menyelamatkan (gate mana, watcher mana) → pembenaran/priorisasi lever berbasis
  bukti, bahan tulisan/laporan Mirza.
Deliverable = **papan komparatif per-case + korpus log baseline yang tercatat
lengkap** (prinsip yang sama dgn claude-play: log adalah harta utamanya).

## 2. Daftar 46 case yang harness MENANG (target baseline, per 2026-07-23 02:15)

Sumber: `swebench_eval.resolved=true` di `../artifacts/f-dev/*`. (Regenerasi:
one-liner §7 — papan bisa berubah bila ada retest baru.)

```
astropy__astropy-14995  astropy__astropy-6938   django__django-10914  django__django-11001
django__django-11039   django__django-11049    django__django-11099  django__django-11133
django__django-11179   django__django-11422    django__django-11620  django__django-11815
django__django-11848   django__django-11964    django__django-12184  django__django-12286
django__django-12453   django__django-12497    django__django-12700  django__django-12708
django__django-12747   django__django-12908    django__django-12915  django__django-12983
django__django-13028   django__django-13033    django__django-13230  django__django-13315
django__django-13447   django__django-13658    django__django-13710  django__django-13757
django__django-14016   django__django-14238    django__django-14382  django__django-14411
django__django-14672   django__django-14752    django__django-14787  django__django-14855
django__django-14915   django__django-15347    django__django-15498  django__django-15790
django__django-15814   django__django-15851
```

## 3. ATURAN MAIN baseline

1. **TANPA harness**: tidak ada fase R/L/F/V, tidak ada gate, watcher, shortlist,
   candidates, oracle-repro wajib, DONE-rejection, rotasi kandidat, reminder
   format, R20-dialek-tolerance, N1/p2 — TIDAK ADA SAMA SEKALI. Yang boleh ada
   hanyalah **loop agentic minimal** (§4). Godaan menambah "sedikit bantuan" =
   merusak validitas ablasi. Kalau ragu sebuah fitur termasuk harness atau
   pipa-minimal, JANGAN tambahkan, catat di README project.
2. **Aturan SWE-bench**: image resmi per case
   (`ghcr.io/epoch-research/swe-bench.eval.x86_64.<case>:latest`), kerja di
   `/testbed` pada base-commit, **gold-blind mutlak** (Gemma hanya menerima
   problem statement; loop DILARANG membaca `cases/gold/`, `swebench_spec.json`,
   artefak harness), tanpa akses jaringan utk mencari solusi.
3. **Model & sampling SAMA dgn harness** (apel-ke-apel): endpoint
   `http://10.8.0.86:8000`, model `gemma-4-31B-it` (cek `/v1/models`), **temp 0.0**.
4. **Wasit SAMA**: `swebench_eval` L2 (`resolved`) — dijalankan loop/orkestrator
   SETELAH run selesai; Gemma tak pernah melihat hasil test gold.
5. **Log = deliverable**: transcript penuh per run (setiap prompt, reply, aksi
   tereksekusi + output, patch akhir) → `console.log` per run dir. Tanpa log
   lengkap, run gagal prosedur.
6. **Endpoint**: eksklusif Mirza, maks 7 lane (memory
   `gemma-endpoint-parallel-lanes`); koordinasikan dgn pemakaian lain (STOP run
   harness masih berlaku; baseline ini DIIZINKAN eksplisit oleh perintah ini,
   tapi konfirmasi jadwal ke Mirza bila ada task Gemma lain berjalan).

## 4. Desain "simple loop" (usulan — finalkan di sesi baru, TDD)

Semangatnya: **loop se-naif mungkin yang masih sah sebagai agen SWE-bench** —
kira-kira setara mini-SWE-agent:
- System prompt pendek: "You are solving a software issue in a repo at /testbed.
  Issue: <problem statement>. You can run shell commands by writing ```bash
  blocks. When you believe the issue is fixed, output DONE." (Bahasa Inggris,
  tanpa trik prompt-engineering — kesederhanaan ADALAH baseline-nya.)
- Loop: kirim messages → parse SATU jenis aksi saja (```bash fence standar) →
  eksekusi di container → append output (tail wajar, mis. 2000 char) → ulang.
- Berhenti bila: model bilang DONE, ATAU budget habis. **Budget = paritas kasar
  dgn harness**: harness memberi ~40 turn/attempt × ≤2-3 attempt per fase;
  baseline yang adil ±**60 turn** single-session (finalkan angka + catat di
  README; jangan diam-diam beda jauh).
- Akhir run: `git -C /testbed diff` → `patch.diff` → wasit swebench.
- **n draw**: mulai **n=1 per case** (temp-0 ~deterministik); naikkan hanya
  dgn keputusan Mirza.
- Transport: pakai pola `chat_with_retry`/timeout dari
  `main/harness/stages/chat_transport.py` sebagai REFERENSI (infra transport =
  pipa, bukan harness — boleh; catat di README bahwa retry transport disamakan).
- Parser fence: parser bash minimal STANDAR saja. **R20-tolerance TIDAK ikut**
  (itu lever harness!). Kalau Gemma emit dialek `call:file:` dan patch-nya jadi
  kosong — ITULAH datanya; jangan "diperbaiki".

## 5. Struktur project & artefak (usulan)

```
gemma-baseline/
  pyproject.toml            # deps: requests/httpx + swebench (uv add)
  baseline.py               # loop inti (kecil, satu file kalau bisa)
  run_batch.py              # antrean case, paralel ≤N lane, resume, state json
  tests/                    # TDD utk parser/loop/penilaian (tanpa endpoint)
  README.md                 # desain final + SEMUA keputusan paritas + cara baca
artifacts-baseline/         # di /Users/mirza/Workspace/gemma-harness-swebench/
  <case>--r1/console.log  patch.diff  swebench_eval.json  meta.json
  papan-baseline-vs-harness.md
```
- Artefak DI LUAR git (konsisten kebijakan artifacts main). Kode & papan
  ringkasan boleh di-git di project baru (init git sendiri; jangan menyentuh
  repo main kecuali menambah handoff/entri katalog hasil).
- `meta.json` per run: case, model, temp, turn_budget, turns_used, done_declared,
  ts, kode-versi-baseline (hash).

## 6. Alur kerja yang kusarankan utk sesi baru

1. Baca handoff ini + `main/docs/kontrak-output.md` (utk memahami apa yang
   SENGAJA tidak diikutkan) + `chat_transport.py`.
2. Bangun project (TDD; suite kecil sendiri, hijau).
3. **Smoke 1 case** yang harness menang mudah & cepat (mis. 15347 atau 11049 —
   kanari stabil) → validasi pipa end-to-end + format log + wasit jalan.
4. Lapor ke Mirza hasil smoke + biaya waktu/turn → minta lampu hijau full-46.
5. Full-46: batch paralel (≤5 lane awal; rolling), pull image per batch
   (`${c}":latest"` — awas modifier zsh), disk cek per batch.
6. **Papan komparatif** per case: harness ✓ vs baseline ✓/✗ (+turns). Kolom
   kunci: "diselamatkan oleh harness?" per case.
7. **Diagnosa komparatif** (protokol per-FAIL Mirza berlaku): utk tiap case
   baseline-FAIL, subagent bandingkan log baseline vs log harness di case yang
   sama → identifikasi mekanisme harness yang menyelamatkan → entri katalog
   `main/docs/katalog-lever.md` ("ablasi <case>: diselamatkan oleh <mekanisme>").
8. Commit rutin (repo baseline), papan + temuan → commit juga entri katalog di
   main. Push bila Mirza minta.

## 7. Perintah berguna

```bash
# Regenerasi daftar 46 (dari main/):
grep -l '"resolved": true' ../artifacts/f-dev/*/swebench_eval.json \
  | sed -E 's|.*/f-dev--([^/]+)--r[0-9]+/.*|\1|' | sort -u

# Endpoint hidup?
curl -s -m 5 http://10.8.0.86:8000/v1/models | head -c 200

# Image (awas zsh modifier):
docker pull "ghcr.io/epoch-research/swe-bench.eval.x86_64.${c}"":latest"
```

## 8. Konteks & jebakan (dari sesi malam 23-jul)

- PASS harness saat ini 46/103 (papan `artifacts/papan-skor-retest-a0i-r20-mac.md`).
- Image SUDAH ada di Mac utk ±15 case (11049/15347/6938/15790/13230/12184/11422/
  11910/15388/14855/15851/12470/14752/13265/15902 + astropy-6938) — sisanya pull.
- Disk: 231Gi bebas; prune container bekas per batch (semalam 65 bangkai = 16GB).
- zsh: `${c}":latest"`; JANGAN `set -- $spec`; dep via pyproject (uv add), JANGAN
  pip ad-hoc (insiden venv semalam: wasit L2 hilang senyap).
- Endpoint eksklusif Mirza; maks 7 lane; `caffeinate` TIDAK menahan clamshell
  sleep — lid terbuka atau `sudo pmset -a disablesleep 1` utk run panjang.
- Jangan jalan bersamaan dgn claude-play batch besar (rebutan docker/disk) —
  claude-play TIDAK pakai endpoint, jadi bisa selang-seling; koordinasikan.

## 9. Pertanyaan terbuka utk Mirza (tanyakan di awal bila belum diputus)

1. Turn budget baseline (usulanku ±60 turn single-session — paritas kasar)?
2. n draw per case (usulanku n=1 dulu, temp-0)?
3. Paralel berapa lane utk full-46 (usulanku 5)?
4. Setelah 46: apakah baseline juga dijalankan pada 57 case gagal (melengkapi
   matriks 103 penuh: harness×baseline 2×2)? Menarik secara riset, tapi biaya
   endpoint — keputusan Mirza.
