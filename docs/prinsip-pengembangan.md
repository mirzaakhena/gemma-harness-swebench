# Prinsip Pengembangan — gemma-harness-swebench

Dokumen baku pemahaman tujuan Mirza (pemilik proyek). WAJIB dibaca bot/agent
yang menerima handoff proyek ini. Bahasa dokumen internal = Indonesia;
SEMUA teks yang dilihat model = English (lihat §4).

Sumber keputusan: percakapan Telegram Mirza ↔ bot-06, 2026-07-18. Update
dokumen ini setiap Mirza menambah/mengubah arah — ini living document.

## 1. Tujuan utama

**Output Gemma harus QUALIFIED SETARA dengan output frontier model, per fase.**
Gemma diberi tugas sempit per fase (mis. REPRODUCE saja — bukan bug-fixing
penuh seperti SWE-bench asli), jadi dia SEHARUSNYA bisa berhasil. Kalau belum
setara → analisa apa yang Gemma butuhkan → perbaiki ARAHAN/harness
(case-agnostic, TANPA hardcode case) → ulangi.

## 2. Metode kerja

- **Per-fase, tuntas satu-satu**: REPRODUCE dulu, lalu LOCALIZE, FIX, VERIFY.
  Jangan mengerjakan e2e sebelum satu fase matang.
- **Kunci satu case dulu** (happy path perdana: `django__django-11422` —
  case yang frontier & Gemma sama-sama pernah solve), baru perluas.
- **Siklus dev per fase**: run frontier (jadi referensi) → run Gemma pada
  input yang SAMA → komparasi log & artefak → analisa gap → improve arahan →
  run Gemma lagi. Berhenti saat Gemma lolos kriteria setara secara stabil.
- **UI-driven**: Mirza mengamati lewat dashboard log (ui/server.py, port
  8766). Dashboard awal sederhana (log stream), tidak fancy.
- **Sub-stage lama (INVESTIGATE/SETUP/REPORT) TIDAK dipakai** — disederhanakan
  (keputusan Mirza): satu loop flat per stage + gate mekanis di ujung.
  Kompleksitas dipindah dari koreografi sub-stage ke pagar kesehatan output.

## 3. Definisi "qualified setara" (kriteria penilaian)

Tiga lapis (lapis 2 = palu keputusan; status: **DISETUJUI Mirza 2026-07-18**
— flip test resmi jadi definisi qualified; terpasang di run_repro_gates
`--gold`, verdict `wrong-logic` bila gagal flip, `pass_l1` = L1+L2):

1. **L1 — gate mekanis** per stage (sudah terpasang): REPRODUCE = anti-vacuous
   / self-contained / idempoten / format; LOCALIZE = format / file-exists /
   rentang ≤200 & ≤EOF. Syarat masuk, bukan bukti setara.
2. **L2 — ekuivalensi fungsional (flip test)**: repro qualified ⟺ FAIL di
   base DAN flip ke PASS saat harness memasang gold patch di container segar.
   Dua repro yang sama-sama flip = fungsional identik, gaya boleh beda.
   Gold HANYA dipakai harness SETELAH model selesai (model tak pernah melihat
   gold — boundary gold-free utuh). Padanan LOCALIZE: file yang ditunjuk ==
   file yang gold patch sentuh.
3. **L3 — rubrik kualitatif** (bahan analisa saat gagal L2, bukan pass/fail):
   fidelitas jalur user (entry point/command sesuai issue), SYMPTOM dalam
   bahasa keluhan user, minimalitas scaffolding, semantik crash
   (crash → FAIL, bukan PASS), tanpa mock atas komponen yang diuji.

## 4. Aturan bahasa (WAJIB)

- **SEMUA yang dilihat model = English**: kontrak stage (*_prompt.md),
  PROTOCOL_NOTE, pesan feedback driver, pesan penolakan DONE, problem
  statement. Token protokol: `DONE` (bukan SELESAI), `REPRO_STATUS: FAIL/PASS`.
  Ada unit test penjaga (test_rejection_messages_are_english).
- **Log (console.log) juga English** — seragam (keputusan Mirza 2026-07-18).
- Dokumen internal (docs/ ini, vault, commit message, chat dgn Mirza) boleh
  Indonesia.

## 4b. Higiene prompt (WAJIB — berlaku untuk SEMUA prompt & skill)

Keputusan Mirza 2026-07-18 (mengulang pengingat lama di vault):

1. **Prompt = instruksi yang model BUTUHKAN untuk fokus, titik.** Jangan
   menulis meta-informasi yang tidak mengubah tindakan model: penjelasan apa
   yang harness lakukan di belakang layar, mekanisme penilaian, alasan
   historis desain. Kriteria output boleh (itu spesifikasi tugas); narasi
   mekanisme enforcement tidak (itu celah gaming + distraksi).
   Contoh salah: "The harness appends the mechanical slots itself...".
   Contoh benar: "Your repro.md contains exactly these lines: ...".
2. **Scope positif, bukan larangan yang menunjuk target.** Larangan eksplisit
   memberi model ide/celah tentang hal yang justru dilarang.
   Preseden vault: "jangan edit file xyz" → ganti "kamu hanya bekerja di
   bawah folder abc". Terapkan pola yang sama di semua kalimat scope
   (mis. "your writable workspace is /testbed/.pipe/" alih-alih "do not
   write outside .pipe / repo is read-only").
3. Enforcement tetap MEKANIS di driver/gate — aturan yang dicabut dari prompt
   TIDAK berarti hilang; dia pindah ke kode (pesan penolakan runtime cukup
   memberi tahu instruksi berikutnya, bukan mekanisme pengawasannya).

## 5. Pembagian beban model vs harness

- **Slot mekanis diisi HARNESS, bukan model** (ringankan model): repro.md →
  model hanya menulis slot interpretif (SYMPTOM/TRIGGER/EXPECTED vs ACTUAL);
  `REPRO COMMAND` + `CONFIRMED-AT-BASE` diisi `compose_repro_md` dari fakta
  yang disaksikan driver. Model tak boleh menyetel slot mekanis (kalau
  menulis, dibuang & diganti).
- **Vonis milik harness**: model tak pernah menulis verdict; event `exit` +
  verdict.json ditulis langkah gate (run_repro_gates / run_localize_gates).
- **Bukti-dulu**: DONE ditolak mekanis sampai driver MENYAKSIKAN bukti
  (REPRODUCE: eksekusi repro.py mencetak FAIL; LOCALIZE: minimal 1 aksi
  eksplorasi bash).
- **Guard tulis**: di LOCALIZE, `file:` hanya boleh menulis /testbed/.pipe/
  (repo read-only bagi model — menutup lubang create_file P24).

## 6. Aturan repo & data (ringkas; detail di kontrak-output.md)

- Emitter tunggal (harness/emit.py); UTF-8 tanpa BOM, LF; append-only;
  rerun = direktori baru r<N+1>; artifacts\ di LUAR git tree, TANPA symlink.
- run_id = `<campaign>--<case_id>--r<N>`; kampanye per fase dev: `r-dev`
  (REPRODUCE), `l-dev` (LOCALIZE), dst. Field `model` belum ada di kontrak
  (kandidat schema 1.1) — sementara lihat `detail.model` di events.
- Semua kode lahir TDD; `python -m pytest` dari root main\ wajib hijau
  sebelum commit. Commit ber-trailer `Agent: <bot>`.

## 7. Konteks & referensi

- Design doc kanonik: vault `2026-07-18 — gemma-harness-swebench — Design
  Fresh Start` (§7 = keputusan eksekusi Mirza).
- Log dev berjalan: vault `R-dev Log — fase REPRODUCE (gemma-harness-swebench)`.
- Dasar empiris desain gate: vault `P25 — Divergence Retrospective — Hasil`.
- Plane: SMARTXRESE-374 (fase REPRODUCE/rewrite, In Progress).
