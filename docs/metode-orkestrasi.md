# Metode orkestrasi claude-play — resep duplikasi persis

Dokumen ini merekam APA YANG DILAKUKAN ORKESTRATOR (sesi Claude utama) pada
eksperimen claude-play supaya metode bisa diduplikasi persis di sesi lain
(kebutuhan handoff). TIDAK memuat perilaku subagent setelah diutus — itu
terekam di `console.log` masing-masing run dir (deliverable korpus).

**Semua path relatif ke root workspace `/Users/mirza/Workspace/gemma-harness-swebench/`**
(berisi `main/` = repo harness ini, `claude-play/` = repo korpus claude-play,
`artifacts/` = artefak Gemma, `artifacts-frontier` = symlink viewer) kecuali
disebut lain.

Asal-usul & aturan main: `claude-play/README.md` +
`main/.handoff/202607230230-prompt-claude-play-referensi-57-case.md`.

> **Terkait:** [[kontrak-output]] · [[sop-rlfv-case-run]] · [[katalog-lever]]

## 0. Prasyarat sesi

- Perintah eval dijalankan dari `main/` (`uv run …`); artefak & papan di
  `claude-play/`.
- Cek disk sebelum tiap batch: `df -h /` (image ~2,2GB/case) dan prune
  container bekas: `docker container prune -f`.
- Symlink viewer (sekali saja): dari root workspace
  `ln -sfn claude-play/artifacts artifacts-frontier` → viewer instance kedua
  (dari `main/`): `uv run python ui/server.py --root ../artifacts-frontier --port 8767`.
- Anti-pattern zsh: pakai `"…${c}"":latest"` saat interpolasi nama image.

## 1. Setup per batch (5 case, keputusan Mirza: paralel per-5)

Per case `<case>`, model `<model>` (haiku|sonnet|opus):

```bash
# run dir (host, di repo claude-play):
mkdir -p claude-play/artifacts/f-claude-<model>/f-claude-<model>--<case>--r1/files

# image (pull bila belum ada; bisa background utk batch berikutnya):
docker image inspect "ghcr.io/epoch-research/swe-bench.eval.x86_64.<case>:latest" \
  || docker pull "ghcr.io/epoch-research/swe-bench.eval.x86_64.<case>:latest"

# container kerja SEGAR per attempt:
docker rm -f "claude-play-<case>-<model>" 2>/dev/null
docker run -d --name "claude-play-<case>-<model>" \
  "ghcr.io/epoch-research/swe-bench.eval.x86_64.<case>:latest" sleep infinity
```

Warning `platform linux/amd64 … arm64` = normal (emulasi, sama dgn harness).

Sanity anti-bocor (cukup sekali per image baru): container TIDAK berisi
`*.patch`/`*.diff` gold; `/testbed` bersih di base-commit
(`git status --short` kosong, `git log -2` = commit lama).

## 2. Pengutusan subagent (Agent tool)

- **5 invokasi Agent dalam SATU pesan** (paralel), `subagent_type:
  "general-purpose"`, `model: "haiku"` / `"sonnet"` / `"opus"`.
- Problem statement DISALIN VERBATIM ke prompt dari
  `main/cases/problems/<case>.txt` — subagent dilarang menjelajah `cases/`.
- Eskalasi: model berikutnya mendapat prompt SAMA (ganti tier + nama
  container + run dir; TANPA info trace pendahulu), container segar.

### 2.1 Template prompt subagent (verbatim; ganti `<CASE>`, `<MODEL>`, `<CONTAINER>`, `<RUNDIR>`, `<PROBLEM_STATEMENT>`)

````
Kamu adalah subagent "claude-play" — memainkan peran MODEL dalam pipeline RLFV, menyelesaikan SATU case SWE-bench secara gold-blind. Model tier: <MODEL>. Case: <CASE>.

## Problem statement (SATU-SATUNYA informasi soal — jangan cari info lain)

<PROBLEM_STATEMENT>

## Lingkungan
- Container docker SUDAH berjalan: `<CONTAINER>`. Repo target di `/testbed` (git, base commit). SEMUA kerja kode lewat: `docker exec <CONTAINER> bash -lc '<cmd>'`
- Untuk perintah python di container, awali: `source /opt/miniconda3/bin/activate && conda activate testbed && ...`
- Menulis file ke container: `docker exec -i <CONTAINER> bash -c 'cat > /path/file' <<'EOF'` … `EOF`
- Run dir kamu di host: `<RUNDIR>` (sudah ada, berisi `files/`). console.log di root run dir; artefak di `files/`.

## ATURAN GOLD-BLIND (pelanggaran = trace cacat, run hangus)
- DILARANG membaca file/dir apa pun di host selain run dir kamu sendiri. Khususnya DILARANG seluruh `/Users/mirza/Workspace/gemma-harness-swebench/main/` dan run dir lain.
- DILARANG akses jaringan/web untuk mencari solusi atau issue aslinya.
- Di container: jangan buang langkah mencari solusi via git history (commit masa depan tidak ada di image).
- DILARANG mengedit file test yang sudah ada di /testbed — fix harus di kode sumber.
- DILARANG pip/conda install atau mengubah dependency env.
- Verifikasi final (test gold) BUKAN urusanmu — orkestrator wasitnya. Kamu boleh menjalankan test yang sudah ada di repo untuk memandu kerja, tapi tidak wajib.

## Prosedur RLFV (urut, bukti-dulu)
R (reproduce):
1. `mkdir -p /testbed/.pipe`; tulis `/testbed/.pipe/repro.py` — oracle mandiri: jalankan skenario problem statement, cetak persis `REPRO_STATUS: FAIL` bila bug termanifestasi, `REPRO_STATUS: PASS` bila tidak (exit code 0 di kedua kasus). Predikat harus menguji observable yang DIKELUHKAN issue, bukan proxy interpretasi penyebab.
2. Jalankan; WAJIB menyaksikan `REPRO_STATUS: FAIL` tercetak sebelum lanjut.
3. Salin repro.py final ke host `<RUNDIR>/files/repro.py`; tulis `<RUNDIR>/files/repro.md` (gejala, perintah repro, expected vs observed di dunia rusak).

L (localize):
4. Investigasi nyata (grep/baca file di /testbed). Tulis `<RUNDIR>/files/candidates.md`: shortlist file kandidat berperingkat; tiap kandidat WAJIB evidence kutipan hasil grep/baca nyata (path + baris), bukan teori.

F (fix):
5. Edit kandidat #1 langsung di container. Jalankan repro. `REPRO_STATUS: PASS` → selesai. Tetap FAIL → revert (`git checkout -- <file>`), coba kandidat #2. MAKSIMAL 2 kandidat.
6. Setelah PASS, ekspor diff ke host:
   `docker exec <CONTAINER> bash -lc "cd /testbed && git add -N -- . ':(exclude).pipe' >/dev/null 2>&1; git diff 2>/dev/null" > <RUNDIR>/files/fix.diff`
   Pastikan fix.diff tidak kosong dan hanya berisi perubahan kode sumber.

## console.log (DELIVERABLE UTAMA — tanpa ini run gagal prosedur walau fix benar)
- Tulis SAMBIL bekerja: append incremental ke `<RUNDIR>/console.log` (pakai tool Write/Edit host), BUKAN sekaligus di akhir.
- Satu entri per langkah, format konsisten:
```
[R#01] $ <perintah>
# why: <alasan satu baris>
<output relevan; pangkas bagian panjang dengan ...>
```
- Prefix fase R#/L#/F#, nomor urut per fase.

## Menyerah
Tulis `SURRENDER: <alasan>` sebagai entri terakhir console.log bila: (a) repro tak kunjung FAIL setelah ~15 langkah substansial, (b) 2 kandidat fix dicoba dan repro tetap FAIL, atau (c) buntu total. Setelah SURRENDER tetap ekspor artefak yang ada (termasuk fix.diff bila ada edit), lalu berhenti.

## Laporan akhir (return value kamu; ≤15 baris)
- Status R / L / F (done/failed/skipped + 1 kalimat masing-masing)
- SURRENDER: ya/tidak (+alasan)
- Jumlah langkah per fase
- 1-2 kalimat insight: titik tersulit case ini
JANGAN sertakan isi console.log penuh di laporan.
````

### 2.2 Penyesuaian per-case yang PERNAH dipakai (batch-1, 2026-07-23)

Diizinkan menambah petunjuk NETRAL (tidak membocorkan lokasi fix/gold), dua
jenis yang sudah dipakai:

- `django__django-15388` — tambahan di ## Lingkungan:
  "Petunjuk teknis netral: repro TIDAK perlu menjalankan server dev sungguhan —
  mekanisme autoreload bisa diuji langsung (fungsi/iterator yang menghasilkan
  daftar file yang dipantau) tanpa proses runserver interaktif. Hindari
  perintah yang blocking/interaktif." (alasan: mencegah subagent memblokir di
  runserver — kendala tooling, bukan petunjuk solusi)
- Klarifikasi observable di R langkah 1 (menegaskan APA yang dikeluhkan issue,
  parafrase dari problem statement saja):
  13265 → "(di sini: crash/error saat menjalankan rangkaian operasi migrasi
  seperti di statement)"; 12470 → "(di sini: arah ORDER BY pada query Child)";
  15902 → "(bila warning deprecation muncul saat memproduksi management form
  formset)". 11910 tanpa penyesuaian.

Batas: penyesuaian TIDAK boleh menyebut file/fungsi target fix — itu bocoran
localize. Juga TIDAK boleh diturunkan dari hasil eval gold attempt sebelumnya
(insiden nyata 2026-07-23: prompt sonnet-12284 sempat diberi "jangan rusak
override manual" — turunan dari P2P gold yang gagal di attempt haiku → agent
di-stop, run dir di-reset, container segar, diutus ulang dgn prompt bersih.
Aturan praktis: sumber penyesuaian HANYA problem statement + kendala tooling
netral).

## 3. Wasit (orkestrator SENDIRI — subagent tak pernah lihat hasil gold)

Setelah subagent selesai & artefak ada (cek `console.log` + `files/fix.diff`
non-kosong):

```bash
cd main
uv run python -m eval.swebench_checker --case <case> --rerun 1 \
  --campaign f-claude-<model> --artifacts ../claude-play/artifacts --timeout 3600
```

(jalankan background — eval container emulasi bisa beberapa menit; checker
menulis `swebench_eval.json` + `files/swebench_test_output.log` sendiri.)

Lalu orkestrator menulis `verdict.json` di run dir:

```json
{
 "schema_version": "claude-play-1.0",
 "run_id": "f-claude-<model>--<case>--r1",
 "case_id": "<case>", "campaign": "f-claude-<model>", "model": "<model>",
 "resolved": true|false,
 "surrender": true|false,
 "steps": {"R": n, "L": n, "F": n},
 "procedural_ok": true|false,      // console.log lengkap ditulis sambil kerja?
 "notes": "<catatan wasit: F2P/P2P, anomali patch, dsb.>",
 "checked_at": "<ISO8601 +07:00>"
}
```

Integritas: patch model TIDAK pernah disunting wasit — dinilai apa adanya
(termasuk hunk tak-disengaja).

## 4. Pasca-vonis

- Update `claude-play/papan-claude-play.md` (✅ / ❌ / 🏳 / …).
- `resolved=false` ATAU SURRENDER → antrekan case utk model berikutnya
  (Haiku→Sonnet→Opus), container SEGAR, prompt sama (§2), tanpa trace
  pendahulu. Stop begitu resolved=true.
- Stop container attempt selesai: `docker rm -f claude-play-<case>-<model>`
  (SETELAH artefak tersalin & vonis keluar).
- Commit repo `claude-play/` tiap batch (log korpus DI-git — beda dgn
  kebijakan `artifacts/` Gemma).
- Diagnosa komparatif (protokol per-FAIL Mirza, dibalik): case yang Claude
  solve tapi Gemma gagal → subagent diagnosa bandingkan trace Claude vs
  diagnosa Gemma di titik macet yang sama → entri katalog "referensi
  komparatif <case>" (kandidat lever) di [[katalog-lever]].

## 5. Keputusan Mirza yang mengikat (2026-07-23)

1. Pilot 10 case dulu → lapor sebelum scale-up 57.
2. Tanpa atap budget; biaya = subscription plan (bukan API credit) → lapor
   konsumsi sebagai kuota sesi, bukan dolar.
3. Kampanye `f-claude-<model>` kompatibel tooling lama (checker via
   `--artifacts`).
4. Pemakaian trace resolved sebagai few-shot Gemma: DIPUTUSKAN NANTI —
   sementara hanya utk desain lever mekanis.
5. Repo terpisah `claude-play/` (skrip+papan+korpus di-git penuh);
   viewer root `artifacts-frontier` (symlink).
6. Lanjut mandiri malam 2026-07-23: setelah batch-1, jalankan 10 case
   berikutnya tanpa menunggu (batch-2 pilot + eskalasi + 5 dari daftar 57).

## 6. Pilot 10 (urutan batch)

Batch-1: 11910, 15388, 13265, 12470, 15902.
Batch-2: 11797, 13768, astropy__astropy-14365, 12284, 15202.
(pemetaan kelas kegagalan Gemma per case: lihat `claude-play/papan-claude-play.md`.)
