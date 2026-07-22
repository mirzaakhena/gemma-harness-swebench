# CLAUDE-PLAY: referensi komparatif 57 case gagal — Haiku→Sonnet→Opus "bermain SWE-bench" di bawah aturan RLFV

**Date:** 2026-07-23 02:3x (WIB)
**Repo kerja:** /Users/mirza/Workspace/gemma-harness-swebench/main (macOS, arm64)
**Branch:** main (HEAD: 28f74a1, sudah di-push ke origin)
**Dari → Ke:** claude-mac (sesi jaga-malam, context penuh) → sesi BARU (Mac ini)
**Lanjutan dari:** `.handoff/202607230200-prompt-malam-retest-pass46-desain-g3.md`
**Perintah asal (Mirza, verbatim intent):** listing semua case yang harness Gemma
gagal → utus subagent **per-5** untuk ikut "bermain di SWE-bench" menyelesaikan
tiap case gagal, **sesuai aturan SWE-bench DAN aturan arsitektur RLFV**. Model:
**Haiku dulu; Haiku menyerah → Sonnet; Sonnet menyerah → Opus.** **YANG TERPENTING:
seluruh informasi log mereka HARUS TERCATAT** — akan jadi referensi belajar bagi
Gemma harness.

---

## 1. Tujuan & kenapa ini berharga

Semua diagnosa kita sejauh ini hanya memotret *bagaimana Gemma gagal*. Trace
Claude di case yang SAMA, di bawah kontrak yang SAMA, memotret *seperti apa
perilaku yang berhasil di titik keputusan yang sama* → mengubah vonis kabur
"kompetensi?" menjadi spec lever konkret. Tangga Haiku→Sonnet→Opus sekaligus
menjadi **gradien kesulitan**: case yang Haiku saja solve ≈ hampir pasti masalah
harness/lever untuk Gemma (bukan kompetensi); case yang butuh Opus = sulit
intrinsik. Deliverable akhir BUKAN angka resolved — melainkan **korpus log
komparatif yang terkatalogkan**.

## 2. Daftar 57 case gagal (103 total − 46 resolved, per 2026-07-23 02:15)

Sumber: `ls cases/problems` minus case dgn `swebench_eval.resolved=true` di
`../artifacts/f-dev/*`. (Regenerasi bila papan berubah — one-liner di §7.)

```
astropy__astropy-12907  astropy__astropy-14182  astropy__astropy-14365  astropy__astropy-7746
django__django-10924   django__django-11019   django__django-11283   django__django-11564
django__django-11583   django__django-11630   django__django-11742   django__django-11797
django__django-11905   django__django-11910   django__django-11999   django__django-12113
django__django-12125   django__django-12284   django__django-12308   django__django-12470
django__django-12589   django__django-12856   django__django-13158   django__django-13220
django__django-13265   django__django-13321   django__django-13401   django__django-13448
django__django-13551   django__django-13590   django__django-13660   django__django-13768
django__django-13925   django__django-13933   django__django-13964   django__django-14017
django__django-14155   django__django-14534   django__django-14580   django__django-14608
django__django-14667   django__django-14730   django__django-14997   django__django-14999
django__django-15061   django__django-15202   django__django-15213   django__django-15252
django__django-15320   django__django-15388   django__django-15400   django__django-15695
django__django-15738   django__django-15781   django__django-15789   django__django-15819
django__django-15902
```

## 3. ATURAN MAIN (tidak bisa ditawar)

1. **Gold-blind MUTLAK** — subagent DILARANG membaca: `cases/gold/`, file
   `swebench_spec.json`, seluruh `../artifacts/` (kecuali run dir miliknya
   sendiri), dan entri `docs/katalog-lever.md`/`docs/koreksi-hipotesis.md`
   tentang case-nya (berisi info gold!). Input SAH hanya: problem statement
   (`cases/problems/<case>.txt`) + isi container. Satu kebocoran = trace case
   itu CACAT sebagai referensi — tandai dan ulang.
2. **Aturan SWE-bench**: kerja di image resmi case
   (`ghcr.io/epoch-research/swe-bench.eval.x86_64.<case>:latest`), repo di
   `/testbed` pada base-commit; dilarang mengakses jaringan utk mencari solusi
   case (git log masa depan tak ada di image — aman by construction).
3. **Arsitektur RLFV** — subagent memainkan peran "model" dalam pipeline penuh,
   menghasilkan artefak kontrak yang SAMA dgn Gemma (`docs/kontrak-output.md`,
   `docs/sop-rlfv-case-run.md`):
   - **R**: tulis `/testbed/.pipe/repro.py` (oracle: cetak `REPRO_STATUS: FAIL`
     di dunia rusak; PASS setelah fix benar) + `repro.md`; WAJIB menyaksikan
     FAIL sebelum lanjut (bukti-dulu, bukan asumsi).
   - **L**: `candidates.md` (shortlist file + evidence per kandidat — evidence
     WAJIB hasil grep/baca kode nyata, bukan teori).
   - **F**: patch via edit nyata di container → `fix.diff` (`git diff`);
     saksikan repro PASS.
   - **V/wasit**: orkestrator (BUKAN subagent) menjalankan
     `eval.swebench_checker` + `eval.fix_gold_eval` — subagent tak pernah
     melihat hasil test gold.
4. **Log = deliverable utama.** Subagent WAJIB menulis `console.log` bergaya
   harness di run dir-nya SAMBIL bekerja: setiap aksi (perintah + alasan
   singkat) dan setiap observasi (output). Format bebas-tapi-konsisten, satu
   entri per langkah. Tanpa console.log lengkap, run dianggap GAGAL prosedur
   walau resolved=true.
5. **Menyerah (definisi operasional)**: subagent menulis `SURRENDER: <alasan>`
   di console.log bila (a) repro tak kunjung FAIL setelah ~15 langkah
   substansial, atau (b) 2 kandidat fix sudah dicoba dan repro tetap FAIL, atau
   (c) buntu total. Orkestrator juga menganggap menyerah bila resolved=false
   pada eval (fix salah = gagal, walau subagent merasa menang).
6. **Eskalasi**: Haiku → Sonnet → Opus. Container SEGAR per attempt; model
   berikutnya TIDAK melihat trace pendahulunya (independen, spt attempt Gemma).
   Berhenti eskalasi begitu resolved=true.

## 4. Arsitektur eksekusi (disiapkan utk sesi baru)

**Struktur artefak (di LUAR papan rate — jangan cemari f-dev):**
```
../artifacts/claude-play/
  <case>/
    haiku--a1/   console.log  repro.py  repro.md  candidates.md  fix.diff
                 verdict.json (ditulis orkestrator: {model, resolved, surrender, ...})
    sonnet--a1/  (hanya bila haiku gagal)
    opus--a1/    (hanya bila sonnet gagal)
  papan-claude-play.md   (case × model → hasil; diupdate incremental)
```

**Loop orkestrator per batch-5** (Mirza: per-5 subagent):
1. Ambil 5 case berikutnya dari antrean → `docker pull` image-nya (cek disk!
   ~2,2GB/image; `df -h` sebelum tiap batch; prune container bekas per batch).
2. Start container per case: `docker run -d --name claude-play-<case>-<model>
   <image> sleep infinity` (pola exec sama spt driver; lihat
   `harness/stages/fix_patch_runner.py` utk idiom docker).
3. Utus 5 subagent paralel (Agent tool, `model: "haiku"`, satu pesan berisi 5
   invokasi). Prompt subagent memuat: aturan §3 verbatim, nama container, path
   problem statement (SALIN isinya ke prompt — subagent tak boleh menjelajah
   `cases/`), path run dir utk console.log & artefak, dan kewajiban lapor
   ringkas (status R/L/F, SURRENDER bila ya + alasan).
4. Setelah tiap subagent selesai: orkestrator salin artefak dari container ke
   run dir, jalankan wasit (`uv run python -m eval.swebench_checker --case
   <case> --rerun 1 --campaign <lihat catatan>` — CATATAN: checker berasumsi
   struktur kampanye; bila repot, tulis skrip kecil `scripts/eval_claude_play.py`
   yang memanggil fungsi checker langsung pada dir claude-play, ATAU buat
   kampanye `f-claude-<model>` mengikuti pola run-dir standar supaya tooling
   lama jalan. PUTUSKAN di sesi baru, dokumentasikan).
5. resolved=false / SURRENDER → antrekan case utk model berikutnya (batch
   eskalasi terpisah, container segar).
6. Update `papan-claude-play.md` + commit log/papan tiap batch (artefak run
   TIDAK di-git — konsisten kebijakan artifacts; papan & skrip DI-git bila di
   repo main).
7. **Diagnosa komparatif** (protokol Mirza per-FAIL tetap berlaku, dibalik):
   utk tiap case yang Claude SOLVE tapi Gemma gagal → subagent diagnosa
   membandingkan trace Claude vs diagnosa Gemma terkatalog di titik macet yang
   sama → entri katalog "referensi komparatif <case>" (kandidat lever).

**Model Agent tool:** `model: "haiku"` / `"sonnet"` / `"opus"` pada parameter
Agent. Subagent TIDAK butuh endpoint Gemma (murni Claude + docker + Bash).

## 5. Rekomendasi eksekusi (pendapatku, Mirza belum memutuskan urutan)

- **PILOT 10 case dulu** sebelum menyapu 57 — pilih lintas kelas kegagalan
  terkatalog supaya tiap kelas dapat pembanding:
  `django__django-11910` (evidence-beracun/oracle), `15388` (salah-mekanisme),
  `13265` (weak-oracle wrong-layer), `12470` (evidence terfabrikasi),
  `15902` (edit-mechanics/P2P), `11422`→SKIP (sudah PASS? CEK — dia menang
  historis; kalau PASS keluarkan), ganti `11797` (streak-48), `13768`
  (intra-reply 72×), `astropy__astropy-14365` (intra-reply + subset-hunk),
  `12284` (intra-hunk blind-spot), `15202` (hapus-guard sekelas 11910).
  Lalu lapor ke Mirza → keputusan scale-up ke 57.
- **Biaya**: 57 case × ≤3 model × run agentic panjang = signifikan. Pilot dulu
  juga demi kalibrasi biaya/case. Paralel 5 = keputusan Mirza, patuhi.
- Jangan jalankan bersamaan dgn batch Gemma di endpoint (tak bentrok resource
  GPU, tapi bentrok docker/disk/perhatian orkestrator — dan STOP run Gemma
  masih berlaku menunggu desain G3).

## 6. Konteks harness yang WAJIB diketahui sesi baru

- **PASS saat ini 46/103** (papan `artifacts/papan-skor-retest-a0i-r20-mac.md`,
  §-A0j di `docs/urutan-retest-lever.md`). 57 gagal = daftar §2.
- Kelas kegagalan Gemma terkatalog (utk diagnosa komparatif §4.7):
  weak-oracle/oracle-eksekusi (R14/N3), P2P-regression, edit-mechanics
  (clobber/quicksand/no-op-edit/truncation), protocol-drift `call:file:`
  (R20 subset TERPASANG), evidence terfabrikasi (R17), intra-reply dedup,
  periode-2 (p2 TERPASANG), streak (N1 TERPASANG). Semua di ekor
  `docs/katalog-lever.md`.
- Idiom docker & kontrak: `harness/stages/run_fix_gemma.py` (pola exec/copy),
  `docs/kontrak-output.md`, `docs/sop-rlfv-case-run.md`.
- Suite test: `uv run pytest -q` → 622 passed (jangan rusak; skrip eval baru
  wajib TDD).
- Memory aktif: `protokol-diagnosa-per-fail`, `target-naikkan-pass-jujur`,
  `gemma-endpoint-parallel-lanes` (endpoint TIDAK dipakai task ini).
- Anti-pattern zsh: `${c}":latest"` (modifier trap), jangan `set -- $spec`.
  Venv: semua dep via pyproject (`uv add`), JANGAN pip ad-hoc.

## 7. Perintah berguna

```bash
# Regenerasi daftar gagal:
ls cases/problems | sed 's/\.txt$//' | sort > /tmp/all.txt
grep -l '"resolved": true' ../artifacts/f-dev/*/swebench_eval.json \
  | sed -E 's|.*/f-dev--([^/]+)--r[0-9]+/.*|\1|' | sort -u > /tmp/pass.txt
comm -23 /tmp/all.txt /tmp/pass.txt        # -> daftar gagal terkini

# Disk & image:
docker system df; df -h /
docker pull "ghcr.io/epoch-research/swe-bench.eval.x86_64.${c}"":latest"
```

## 8. Pertanyaan terbuka utk Mirza (tanyakan di awal sesi baru bila belum dijawab)

1. Pilot-10 dulu atau langsung 57?
2. Budget biaya/atap token utk tangga Opus?
3. Kampanye eval: buat `f-claude-<model>` (kompatibel tooling lama) atau skrip
   eval khusus claude-play? (rekomendasiku: kompatibel tooling lama)
4. Apakah trace Claude yang resolved=true boleh dipakai jadi few-shot/prompt
   material utk Gemma, atau HANYA utk desain lever mekanis? (isu batas
   mekanis-vs-prompt yang sudah lama tercatat)
