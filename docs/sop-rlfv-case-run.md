# SOP — Menjalankan & Membedah Case SWE-bench (pipeline RLFV)

Dibuat 2026-07-20 (bot-01), diturunkan dari 11 case yang dijalankan penuh dalam satu
sesi. Dokumen internal, bahasa Indonesia.

**Untuk siapa:** bot/agent yang menerima handoff proyek ini dan diminta menjalankan case
SWE-bench lewat pipeline RLFV (REPRODUCE → LOCALIZE → FIX → VERIFY).

**Sifat dokumen:** deskriptif, bukan checklist steril. Tiap aturan disertai **alasannya**,
karena kamu akan menemui situasi yang tidak persis sama dan harus memutuskan sendiri.
Aturan tanpa alasan akan kamu langgar di saat yang salah.

**Baca juga:** `prinsip-pengembangan.md` (arah dari Mirza), `katalog-lever.md` (perbaikan
harness yang tercatat), `koreksi-hipotesis.md` (klaim yang sudah dibantah — jangan
mengulanginya), `kontrak-output.md` (kontrak data).

---

## 0. Prinsip induk yang menjelaskan hampir semua aturan di bawah

1. **Fisika > instruksi.** Lever yang mengikat mekanis di titik vonis jauh lebih efektif
   daripada menambah kalimat ke prompt. Bukti proyek konsisten: perbaikan prompt ±17%
   efektif; lever L#1/L#2/L#3 di fase LOCALIZE nol efek.
2. **`resolved=true` BUKAN berarti patch benar.** Ini pelajaran termahal sesi ini.
   `resolved=true` artinya "tidak ada test resmi yang gagal". Sudah terbukti tiga kali
   berbeda bahwa itu tidak sama dengan benar (lihat §4).
3. **Bukti > pembacaan.** Untuk klaim tentang alat ukur, jalankan alat ukurnya terhadap
   input yang sengaja rusak. Membaca kode menghasilkan klaim benar tapi lemah.
4. **Boundary gold-blind.** Product harness (R→L→F) tidak pernah melihat gold. Semua
   evaluasi vs gold hidup di `eval/`. Jangan pernah membocorkan gold ke loop model.

---

## 1. Menjalankan satu case — prosedur

### 1a. Aturan GPU (WAJIB, sering dilanggar)

GPU vLLM dipakai bersama owner lain. Sebelum **setiap** run yang memanggil Gemma
(`run_reproduce_gemma`, `run_localize_gemma`, `run_fix_gemma` — TIDAK berlaku untuk
gate/eval/checker yang hanya memakai docker):

```
python C:\Users\Mirza\workspace-shared\smartm2m-bench\swe\harness-uplift\swebench-original\gpu_check.py
```

Lanjut **hanya** kalau baris terakhir menunjukkan `waiting == 0`. Kalau > 0: tunggu
**10 detik** (bukan 15 — celahnya sempit dan sering kosong tiba-tiba), cek lagi.

**Bungkus polling + eksekusi dalam SATU panggilan foreground.** Kalau kamu poll dulu lalu
eksekusi di panggilan terpisah, celahnya bisa direbut proses lain di antara keduanya.

**Jalankan case secara SERIAL, satu run Gemma pada satu waktu.** Alasannya bukan sopan
santun: dua sesi Gemma bersamaan saling mengisi antrean vLLM sehingga `waiting` tidak
pernah nol, dan aturan `gpu_check` jadi macet saling menunggu. Throughput juga tidak
bertambah karena GPU-nya sama. Cek `docker ps` dan tunggu sampai tidak ada container
`gemma-work-*` milik case lain.

**Data empiris sesi ini:** ketika serial dijaga, tunggu GPU 0–7 detik per case (rasio
tunggu:eksekusi sampai 1:74). Ketika sempat tumpang tindih, satu case menghabiskan 23 dari
30 menit hanya untuk menunggu. Bottleneck-nya kita sendiri, bukan owner lain.

### 1b. Invokasi per fase

Semua dari root `main\`, semua pakai `python -m` (BUKAN `python harness/stages/x.py` —
docstring modul masih menulis pola lama yang salah).

```
python -m harness.stages.run_reproduce_gemma --case <ID> --rerun <N> --image <IMG> --problem-file cases\problems\<ID>.txt
python -m harness.stages.run_repro_gates     --case <ID> --rerun <N> --image <IMG> --gold cases\gold\<ID>\gold.patch
python -m harness.stages.run_localize_gemma  --case <ID> --rerun <N> --image <IMG> --input-files <dir files run R qualified> --problem-file ...
python -m harness.stages.run_localize_gates  --case <ID> --rerun <N> --image <IMG>
python -m eval.localize_gold_eval            --case <ID> --rerun <N> --gold cases\gold\<ID>\gold.patch
python -m harness.stages.run_fix_gemma       --case <ID> --rerun <N> --image <IMG> --input-localize-files <dir files run L qualified> --input-repro-files <dir files run R qualified> --problem-file ...
python -m harness.stages.run_fix_gates       --case <ID> --rerun <N> --image <IMG> --input-repro-files <dir files run R qualified>
python -m eval.swebench_checker               --case <ID> --rerun <N>
python -m eval.fix_gold_eval                  --case <ID> --rerun <N> --gold cases\gold\<ID>\gold.patch
```

Jalankan `--help` tiap driver sebelum mulai. Murah, dan sekali waktu menyelamatkan.

**Progres driver ditulis ke `console.log` di run dir, BUKAN stdout.** Stdout yang sepi itu
normal, bukan tanda hang. Cek progres lewat `events.jsonl` (`budget.msg_used`) atau
`docker ps`.

### 1c. Aturan rerun dan input beku

- Tidak qualified → rerun dengan nomor **baru** (`--rerun 2`, lalu `3`). **Append-only
  mutlak**: jangan pernah menimpa atau menghapus run dir lama.
- Maksimal **r3** per fase. Gagal ketiganya → berhenti, laporkan kelas kegagalannya
  (kelompokkan `detail.why` dari event retry menjadi kelas, jangan tempel mentah), jangan
  lanjut ke fase berikutnya.
- **Input beku antar-fase = run yang QUALIFIED**, dicek lewat `verdict.json` → `pass_l1`,
  **bukan nomor rerun terbesar**. Contoh nyata: 13660 R r3 divonis `wrong-logic`, yang
  qualified terakhir r2.
- Verifikasi run L qualified punya `files\candidates.md` — fase FIX membutuhkannya. Run L
  dari era lama sering belum punya.

### 1d. Setup case baru

Pola reusable (turunan `prepare_10914.py`): ambil `problem_statement` + `patch` dari
dataset HF `princeton-nlp/SWE-bench_Lite` → `cases/problems/<ID>.txt`,
`cases/gold/<ID>/gold.patch` + `gold.json`. Lalu:

```
python -m eval.fetch_swebench_spec --case <ID> [--case <ID> ...]
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.<ID>:latest
```

Butuh shim `resource` di Windows sebelum import `datasets`. Tulis file pakai Write/Edit,
**jangan heredoc/Set-Content** (mojibake).

**Disk:** cek sisa disk setiap beberapa pull dan berhenti kalau menembus ~12 GB. Kabar
baik: base layer Django dipakai bersama, jadi 10 image tambahan hanya memakan ~0,4 GB.
**Jangan pernah menghapus image/container/volume untuk mengosongkan tempat** — itu
keputusan pemilik, bukan agent. Laporkan dan minta keputusan.

---

## 2. Memilih case berikutnya

**Kriteria yang terbukti prediktif: seberapa banyak yang harus DITEBAK model dari problem
statement.** Bukan ukuran patch, bukan tier Papan 103 saja.

Papan 103 menandai case "mudah" berdasarkan **baseline** — Gemma diberi problem statement
+ repo dan langsung menulis patch, dinilai test resmi. Pipeline kita menuntut hal berbeda:
model harus **menulis dulu alat ukurnya sendiri** (`repro.py`) baru menulis patch yang
lolos alat ukur buatannya. Dua kemampuan bertumpuk. Karena itu "mudah di baseline ≠ mudah
di REPRODUCE" (10914: baseline cuma ganti 1 baris, REPRODUCE makan 10 attempt).

Gradien yang dipakai sesi ini, dari termudah:

1. Problem statement memuat **kode fix-nya verbatim** (13658, 11039)
2. Menyebut file + nomor baris + perilaku target (11179, 14382)
3. Menyebut nama API/fungsi tapi bukan kodenya (14238, 13590)
4. Hanya traceback / keinginan, arah fix harus diciptakan (11583, 13710, 13028)

Faktor pengubah: **jangkar konteks**. Case yang fix-nya harus diciptakan sendiri tapi
punya pola tetangga untuk ditiru (mis. blok `except FileNotFoundError: continue` tepat di
atas titik fix) ternyata lebih mudah daripada yang patch-nya kecil tapi menuntut
pengetahuan internal yang tidak disinggung sama sekali.

---

## 3. Protokol pemeriksaan WAJIB tiap case

Ini bagian yang paling mudah terlewat dan paling banyak menghasilkan temuan. Jangan
laporkan case sebagai "berhasil" sebelum keempatnya dijalankan.

### 3a. Cek lulus palsu

Laporkan **selalu**, bahkan saat hijau:

- `resolved` dari `swebench_eval.json`
- `file_match` dan `line_overlap` dari `gold_eval.json`

**`resolved=true` DENGAN `file_match=false`** → tandai tegas sebagai kandidat lulus palsu
dan jelaskan kenapa test resmi bisa lolos. Sudah terjadi sekali (13658: patch di file
yang salah).

**Jebakan teknis:** `line_overlap` bisa bernilai **`null`**, bukan `false`. Kalau kamu
membulatkan `null`, satu-satunya hit di korpus hilang.

**Recall detektor ini rendah**, dan kamu harus tahu itu: dua lulus-palsu lain (12915,
12286) keduanya `file_match: true`. Jadi `file_match=true` **tidak** membuktikan patch
benar — lanjut ke 3b.

### 3b. Bandingkan patch dengan gold, secara semantik

Bukan diff-vs-diff. Pertanyaannya: **setara / lebih sempit / lebih ketat / lebih longgar?**

Kategori yang sudah ditemui:

- **Setara walau beda tulisan** — 11179 (`instance.pk = None` vs `setattr(...)`; diverifikasi
  dengan membuka `base.py:571` di dalam image, bukan diasumsikan). 14238
  (`any(issubclass(...))` vs `issubclass(x, tuple)`).
- **Lebih ketat** — 11099 (memperbaiki dua anchor, gold hanya satu).
- **Lebih sempit** — 12286 (fallback satu tingkat vs penelusuran bertahap).
- **Lebih longgar / melanggar disiplin non-fungsional** — 12915 (menghilangkan
  `sync_to_async` sehingga memblokir event loop; tidak ada test yang mengukur blocking).
- **Lulus palsu** — 13658 (file salah, plus regresi diam-diam di call site lain).

Periksa juga hal yang tidak diukur test: komentar yang jadi berbohong terhadap kodenya
(11039), logika yang bocor ke kelas generik untuk menambal satu pemanggil (13658), call
site lain yang ikut berubah perilaku.

### 3c. Nilai kualitas repro — empat poin

`repro.py` adalah **satu-satunya yardstick fase FIX**. Kalau ia longgar, seluruh vonis L1
kehilangan makna. Nilai:

- **(a) Cakupan** — apakah menguji SEMUA jalur yang disentuh gold? Sinyal cepat: gold
  punya ≥2 hunk sementara repro hanya memanggil satu API sekali.
- **(b) Kekuatan assert** — meng-assert nilai/struktur, atau sekadar "tidak melempar
  exception"? Substring atas stdout termasuk lemah.
- **(c) Polaritas cabang error** — adakah cabang yang berujung PASS? Pola berbahaya:
  `if <gejala>: FAIL else: PASS`, karena semua kegagalan katastrofik mendarat di PASS.
  Catatan penting: **pola sintaktis ini saja tidak cukup** — banyak yang punya penjaga
  exception yang membelokkan crash ke FAIL. Yang dihitung adalah perilakunya (§3d).
- **(d) Kontrol positif** — adakah verifikasi bahwa operasi normal masih jalan, DAN apakah
  verifikasi itu benar-benar ikut menentukan kelulusan (bukan sekadar dicetak lalu
  diabaikan)? **19 dari 23 case tidak punya.** Contoh yang punya dan load-bearing: 14382
  menjalankan `startapp control_app control_dir` lebih dulu dan langsung ERROR kalau gagal.

Selalu tutup dengan: **sebutkan contoh konkret fix under-general yang akan LOLOS repro
ini.** Kalau kamu tidak bisa menyebutkannya, kamu belum benar-benar menilai repronya.

### 3d. Eksperimen sabotase (yang membuat penilaian di atas jadi angka)

Ini metode paling produktif yang lahir sesi ini. Membaca kode menghasilkan klaim benar
tapi lemah; menjalankannya menghasilkan angka yang tidak bisa didebat.

Jalankan container **terpisah** dari image yang sama (beri nama khas, mis. `probe<ID>`),
lalu ukur:

- **Baseline** tanpa patch → seharusnya `REPRO_STATUS: FAIL`
- **Sabotase A** — gold fix diterapkan BENAR, tapi satu operasi inti yang tidak berhubungan
  dirusak (mis. `QuerySet.create()` raise) → apakah repro tetap PASS?
- **Sabotase B** — file repo ditinggalkan dalam kondisi `SyntaxError` → tetap PASS?
- **Sabotase C** — framework sama sekali tidak bisa di-import → tetap PASS?
- **Sabotase D** — fix yang mematikan gejala tapi merusak semantik (rancang sesuai bug case)

**Jebakan yang sudah memakan korban:** pakai interpreter testbed
(`/opt/miniconda3/envs/testbed/bin/python`), **bukan `python` sistem**. Sekali salah
interpreter, baseline ikut mencetak PASS dan seluruh hasil probe jadi menyesatkan.

**Wajib bersih-bersih:** hentikan dan hapus container probe, `git checkout` semua
perubahan. Jangan pernah menyentuh container atau artefak run resmi.

Metode yang sama berlaku untuk mengukur daya beda **test resmi F2P**: pasang patch yang
jelas ngawur di titik gold dan lihat apakah F2P tetap lulus. Begitulah ditemukan bahwa
daya beda `test_program_name_from_argv` seluruhnya crash-vs-tidak-crash.

---

## 4. Membaca hasil dengan jujur

**`resolved=true` bukan berarti patch benar.** Tiga bukti berbeda jenis:

- **12915** — patch benar secara nilai kembalian tapi memblokir event loop. Test tidak
  mengukur blocking. **Batas metodologi**, bukan cacat harness — memperbaiki test suite
  SWE-bench berarti berhenti mengukur SWE-bench.
- **13658** — patch di file yang salah, lolos karena daya beda test-nya ternyata hanya
  crash-vs-tidak-crash. Plus regresi diam-diam yang 181 P2P tidak lihat.
- **12286** — fallback satu tingkat, divergensi nyata pada konfigurasi yang tidak dibangun
  test mana pun.

**Hijau juga bukan bukti yardstick bekerja.** Beberapa case hijau karena model kebetulan
menulis fix yang lebih benar daripada yang dituntut repro (11099: repro tidak pernah
menguji anchor depan, jadi fix minimal pun lolos). Jangan hitung hijau semacam itu sebagai
validasi gate.

Karena itu **laporkan papan skor dengan pembedaan**: hijau asli vs hijau palsu vs merah.
Angka agregat tanpa pembedaan itu menyesatkan pemilik proyek.

---

## 5. Autopsi setiap case → katalog lever

**Aturan tetap (keputusan Mirza):** setiap satu RLFV selesai, utus **satu subagent** untuk
membedah lognya, hasilnya masuk `docs/katalog-lever.md`, lalu **langsung commit**.

Jalankan autopsi **serial, tidak paralel** — semuanya menulis ke file yang sama dan bisa
saling menimpa. Tidak memperlambat apa pun karena autopsi tidak memakai GPU.

### Aturan katalog yang harus dipatuhi subagent

1. **Baca katalog sampai habis dulu** sebelum menulis apa pun.
2. **Append-only.** Entri yang sudah divonis beku; perkembangan baru ditulis sebagai baris
   tambahan bertanggal di bagian Status, bukan dengan menulis ulang diagnosa lama.
3. **Satu mekanisme = satu lever.** Case kedua dengan tanda tangan sama masuk sebagai
   *bukti penguat*, bukan entri baru.
4. **Bar untuk entri baru TINGGI**, dan makin tinggi seiring waktu. Katalog sudah jenuh:
   enam autopsi terakhir menghasilkan nol mekanisme baru. Itu **bukan kegagalan** autopsi —
   itu sinyal bahwa nilai marjinalnya bergeser dari menemukan kelas ke **mengukur
   frekuensi**.
5. **Kandidat yang ditolak WAJIB dicatat** di catatan penutup, lengkap dengan alasan dan
   **syarat kapan boleh dinaikkan**. Ini yang mencegah katalog jadi tempat sampah keluhan.
6. **Bedakan tegas akar-model / akar-harness / batas metodologi** di bagian Diagnosa.
   Lever yang menyerang akar yang salah adalah cara termahal untuk belajar.
7. **Prioritaskan usulan mekanis** (gate/driver/API/kontrak eksekusi). Usulan yang isinya
   "tambah kalimat ke prompt" harus punya alasan khusus kenapa jalur mekanis tidak mungkin.

### Ketika katalog sudah jenuh

Geser fokus autopsi dari "cari lever baru" ke **"ukur frekuensi kelas yang sudah
tercatat"**. Frekuensi yang menentukan urutan pemasangan, dan itu yang biasanya kurang.
Sebut angka **absolut dan denominatornya**, dan katakan berapa yang benar-benar kamu
periksa kalau kamu hanya sempat sebagian — jangan mengekstrapolasi diam-diam.

---

## 6. Disiplin epistemik (ini yang paling membedakan hasil)

### 6a. Beri subagent izin eksplisit membantah pemanggilnya

Saat mengutus subagent, sertakan fakta yang sudah kamu ketahui **plus perintah
memverifikasi sendiri** ("verifikasi sendiri, jangan telan mentah"). **Enam dari sepuluh
koreksi** di `koreksi-hipotesis.md` lahir dari mekanisme ini — termasuk koreksi terhadap
kesimpulan yang sudah terlanjur dilaporkan ke pemilik proyek.

Kalau subagent membantahmu dan buktinya kuat, **verifikasi sendiri lalu koreksi ke pemilik
proyek secara eksplisit**. Jangan diam-diam memperbaiki.

### 6b. Catat koreksi di `koreksi-hipotesis.md`

Bedakan tiga derajat, jangan disamakan:

- **TERBANTAH** — dibuktikan salah
- **TIDAK DIDUKUNG** — bukti tidak cukup, belum tentu salah
- **DIPERSEMPIT** — benar tapi lebih sempit dari yang dinyatakan

Wajib menyebut **bukti pembantahnya**, bukan sekadar "ternyata salah". Kalau pembantahnya
eksperimen, tulis cukup detail supaya bisa diulang.

### 6c. Dua bias yang terbukti berulang pada kami

- **Melompat dari korelasi ke kausalitas.** Bentuknya selalu sama: dua hal terjadi
  bersamaan, yang paling menarik ditunjuk sebagai sebab, tanpa memeriksa komposisi
  kelompok atau sebab alternatif. Sebelum membaca rasio, **cek komposisi kelompoknya** —
  rasio LV-09 (1/5 vs 6/7) ternyata praktis mengukur satu case yang diulang tiga kali.
- **Terlalu cepat menamai kelas baru.** Menamai terasa seperti kemajuan padahal sering
  hanya memindahkan label.

---

## 7. Commit & pelaporan

- **Commit segera setiap autopsi selesai** (keputusan Mirza), jangan menunggu menumpuk.
- Commit message memuat **angka dan koreksi**, bukan cuma "update katalog". Commit message
  adalah tempat pertama orang mencari kenapa sesuatu berubah.
- Trailer `Agent: <nama-bot>` wajib.
- **PowerShell:** pesan commit yang memuat tanda kutip ganda akan memecah parsing
  here-string. Tulis pesan ke file lalu `git commit -F <file>`.
- Data case baru (`cases/problems/`, `cases/gold/`) juga di-commit — kalau tidak, setup
  hilang bersama mesin.
- **Lapor pemilik proyek per fase**, bukan hanya verdict akhir, supaya kelihatan patahnya
  di mana kalau patah.

---

## 8. Bug harness yang diketahui — CATAT, JANGAN PERBAIKI

Status semua lever di katalog: **BELUM DITERAPKAN** (keputusan Mirza: catat dan commit
segera, jangan diterapkan sampai diinstruksikan). Kalau kamu menemui gejalanya, catat
angkanya dan lanjut.

Yang paling sering terpicu — **LV-09**: `run_reproduce_gemma.py:286` dan
`repro_sandbox_runner.py:35-36` mengirim `pipe_runtime.py` ke container, tetapi
`run_fix_gemma.py:231-232` hanya menulis `repro.py`. Repro yang mengandung
`from pipe_runtime import App` mati `ModuleNotFoundError` di loop kerja fase FIX.

**Yang WAJIB kamu pahami supaya tidak salah lapor:** ini merusak **loop iterasi model**,
**bukan validitas vonis**. Pre-check DONE dan gate memakai `evaluate_patch_in_fresh_world`
yang sama dengan argumen `args.input_repro_files` yang sama, dan sandbox menyalin
`pipe_runtime.py`. Vonis `flip` tetap sah. Kesimpulan sebaliknya sudah pernah dibuat dan
dibantah (KH-02).

Laporkan dengan angka: apakah `repro.py` tiap rerun mengimpornya, dan berapa kejadian
`No module named 'pipe_runtime'` di `console.log` fase FIX.

---

## 9. Anti-pattern yang sudah benar-benar terjadi

- ❌ **Menaruh pekerjaan di background lalu mengakhiri turn.** Subagent RLFV pertama
  melakukannya dan melapor "selesai" padahal pipeline belum jalan sama sekali. Semua
  eksekusi **foreground**, dan jangan akhiri turn sampai selesai atau kena kondisi
  berhenti yang terdefinisi. Perintah kena timeout → **ulangi**, jangan menyerah.
- ❌ **Menyamakan "agent berjalan" dengan "pipeline berjalan".** Verifikasi ke artefak
  (`ls` run dir), bukan ke status agent.
- ❌ **Melaporkan hijau tanpa memeriksa `file_match`.**
- ❌ **Menerapkan lever** padahal statusnya rekomendasi.
- ❌ **Mengekstrapolasi angka** dari sampel yang tidak kamu periksa.
- ❌ **Menghapus image/container/volume** untuk mengosongkan disk tanpa persetujuan.
- ❌ **Menimpa run dir lama** atau mengedit handoff/plan yang sedang diikuti.
- ❌ **Menulis file pakai heredoc/Set-Content** di Windows (mojibake). Pakai Write/Edit.

---

## 10. Ringkasan siklus per case

1. `gpu_check` sampai `waiting == 0` + tidak ada `gemma-work-*` case lain
2. REPRODUCE → gate (+flip). Tidak qualified → rerun sampai r3
3. LOCALIZE → gate + `localize_gold_eval`. Pastikan ada `candidates.md`
4. FIX → gate
5. `swebench_checker` (VERIFY L2) + `fix_gold_eval`
6. **Pemeriksaan §3**: lulus palsu → patch vs gold → kualitas repro (a-d) → sabotase
7. Lapor pemilik proyek: hasil per fase + papan skor yang membedakan hijau asli/palsu
8. Utus subagent autopsi → katalog lever (serial)
9. **Commit** katalog + data case
10. Koreksi apa pun yang muncul → `koreksi-hipotesis.md`, dengan derajat dan buktinya
