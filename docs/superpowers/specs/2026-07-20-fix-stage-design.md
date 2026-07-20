# Spec Desain — Stage FIX (kampanye `f-dev`)

Status: menunggu review Mirza. Sumber keputusan: vault "Desain Stage FIX —
Keputusan Brainstorm (gemma-harness-swebench)" (sesi Telegram 2026-07-20,
semua butir disetujui Mirza) + kontrak-output.md + prinsip-pengembangan.md +
vault Prinsip Stabilisasi §2-§3. Dokumen bahasa Indonesia; SEMUA teks yang
dilihat model = English (prinsip-pengembangan §4).

## 1. Tujuan & definisi sukses

Stage FIX: Gemma mengedit source repo agar bug hilang. Yardstick = `repro.py`
beku warisan fase R (terbukti flip: FAIL di base, PASS bila bug diperbaiki).

- **Sukses (product, gold-blind):** patch model membuat `repro.py` PASS di
  container SEGAR (pair 2×). Verdict run: `flip`.
- **Gagal:** seluruh kandidat shortlist habis tanpa PASS → `no-flip`.
- **Dua realm (framing Mirza):** product tidak pernah melihat gold; kebenaran
  vs gold dinilai TERPISAH di lapisan test-system (`eval/fix_gold_eval.py`,
  §8) — penangkap false-PASS (patch special-casing repro / salah arah).

## 2. Arsitektur loop — harness-driven iterasi kandidat

```
input: candidates.md (run L qualified TERAKHIR case itu; 2-3 kandidat, tanpa prioritas)
for kandidat in urutan-candidates.md:            ← HARNESS yang memilihkan
    attempt = sesi Gemma FRESH CONTEXT           ← nol kontaminasi antar attempt
    container kerja BARU dari base image         ← pristine by construction
    loop percakapan (bash) sampai DONE-diterima / budget habis
    DONE diterima (pre-check pair PASS di dunia segar) → run sukses, STOP
gagal semua kandidat → verdict no-flip
```

- Model TIDAK pernah melihat kandidat lain (anti context-pollution; pemilihan
  = titik lemah terbukti fase L, diambil alih harness by construction).
- Atribusi murni: attempt ke-N menang ⇒ kandidat ke-N adalah situs fix.
- Kandidat = paket solusi (prinsip); implementasi sekarang single-file —
  riset 2026-07-20: 18/18 gold populasi single-file, 6/18 multi-hunk.
  Multi-lokasi dalam SATU file didukung otomatis (model mengedit file
  langsung). Dukungan paket multi-file = non-goal (YAGNI, dicek ulang saat
  ekspansi populasi).

## 3. Seed per attempt (pesan pertama, English)

1. Problem statement (`cases/problems/<case_id>.txt`).
2. `repro.md` verbatim (definisi salah/benar dari fase R).
3. **Isi `repro.py`** (pelajaran P21: model melihat lembar ujiannya).
4. Kandidat AKTIF saja dari candidates.md: file + evidence + expectation.
   Kandidat lain tidak disebut (scope positif).
5. Kontrak stage (`fix_prompt.md`, §5).

Tidak ada whitelist baca: eksplorasi read-only bebas via bash.

## 4. Sesi dalam attempt — driver `run_fix_gemma.py`

Pola driver R/L (gemma_protocol; done-rejection; telemetri kaya):

- **Bash penuh** di container kerja: baca file, eksperimen, jalankan
  `repro.py` sendiri untuk feedback cepat.
- **Bukti-dulu:** DONE ditolak sampai driver MENYAKSIKAN eksekusi `repro.py`
  model mencetak PASS di container kerja (standar token TUNGGAL baris-eksak
  `exact_status`, pola R).
- **Pre-check DONE (vonis dunia segar):** harness `git diff` container kerja
  → apply ke container SEGAR (mekanisme `repro_sandbox_runner.py --patch`,
  reuse flip-test) → `repro.py` BEKU 2× → keduanya PASS → DONE diterima.
  State bengkel tidak pernah dipercaya. Salinan repro.py vonis selalu dari
  artefak fase R — edit model atas repro.py di container kerja tak berpengaruh.
- **Pagar edit (mekanis, bukan larangan prompt):** diff sah = hanya menyentuh
  file kandidat aktif. Diff kosong / menyentuh file lain → DONE ditolak +
  feedback konkret (nama file nyasar / fakta kosong). Prompt memakai scope
  positif ("your edit site is `<file>`").
- **Feedback kaya + standar tunggal:** penolakan DONE membawa alasan konkret
  (exit + tail output pair); definisi "PASS" identik di mid-loop, pre-check,
  dan gate (Prinsip Stabilisasi §4).
- **Budget:** msg_limit per attempt = default driver L (angka final dikunci
  saat implementasi, konsisten stage lain). Budget habis → attempt gagal →
  kandidat berikutnya.
- Attempt berikutnya = container kerja baru + sesi baru (tidak ada reset
  in-place; pristine by construction).

## 5. Kontrak prompt `fix_prompt.md`

- English, higiene §4b (tanpa narasi mekanisme enforcement), scope positif,
  ultra-slim default mengikuti keputusan pasca-A/B fase R; dua-tier
  rule:/detail via `rule_catalog` bila perlu injeksi.
- Isi inti: tujuan (make the frozen repro pass by fixing the bug at the
  given site), spec `fix.md` (slot interpretif WHAT CHANGED / WHY), token
  protokol (DONE, status line), arahan menjalankan repro untuk observasi.
- Slot mekanis `fix.md` (file tersentuh, hasil repro, kandidat pemenang)
  diisi HARNESS (pola `compose_repro_md`); tulisan model di slot mekanis
  dibuang & diganti.

## 6. Artefak & events (kontrak-output 1.0.0 — tanpa perubahan schema)

- `run_id` = `f-dev--<case_id>--r<N>`; append-only; rerun = r<N+1>;
  satu run = satu case = satu siklus penuh iterasi kandidat.
- `events.jsonl`: `phase:"fix"`; field `attempt` = nomor kandidat (mulai 1).
  Event `retry` utk penolakan DONE (detail terstruktur: alasan, pair
  status/exit/tail — SEJAK HARI PERTAMA, Prinsip Stabilisasi §5); `exit`
  sekali di akhir run membawa verdict.
- `verdict.json`: `phases.fix.verdict` ∈ `flip | no-flip | timeout | abort`
  (enum kontrak §4; `empty-patch` dipakai level-attempt di detail, bukan
  verdict run). `pass_l1` = vonis mekanis gold-free run (flip ⇒ true).
- `files/`:
  - `fix.diff` — diff attempt PEMENANG (kontrak §10; via `git diff`,
    file baru ter-cover `git add -N`).
  - `fix.md` — interpretif model + mekanis harness.
  - `attempts/attempt-<k>.diff` (+ catatan ringkas per attempt) — telemetri
    kandidat gagal, bahan autopsi.
- `campaign.json` f-dev dibuat saat kampanye dimulai (emitter tunggal
  `harness/emit.py`; UTF-8 tanpa BOM, LF).

## 7. Gate `run_fix_gates.py` (product, L1)

Definisi kebenaran IDENTIK dgn pre-check (standar tunggal):

1. `fix.diff` non-empty & apply bersih di container segar.
2. Diff hanya menyentuh file kandidat (source; bukan test file / repro).
3. Repro pair 2× di dunia segar ber-patch → PASS keduanya ⇒ `flip`.
4. Format `fix.md` sah (slot lengkap).

Gate = lapisan terakhir yang menulis verdict (vonis milik harness).

## 8. Eval development `eval/fix_gold_eval.py` (test-system, gold)

CLI `--case --rerun` pola `localize_gold_eval.py`; output `gold_eval.json`
per run:

- `file_match`: file yang disentuh fix.diff == file gold (reuse
  `gold_touched_files()`).
- `overlap`: irisan rentang hunk vs `gold_line_ranges()` — advisory.
- Fungsi utama: menandai **false-PASS** (flip product tapi file/arah ≠
  gold) utk autopsi manusia. Tidak pernah diumpankan ke loop model
  (boundary integritas).

## 9. Populasi awal & input beku

13 case (12 daftar handoff + 12747 [3/3 pasca-L-a]): 11422 · 11999 · 12308
· 13401 · 13220 · 11964 · 11910 · 13660 · 14017 · 15400 · astropy-7746 ·
13768 · 12747. Menyusul opsional: 15320 (2/3), 13158 (1/3). Input beku per
case = `candidates.md` + `repro.md` + `repro.py` dari run qualified TERAKHIR
fase masing-masing (`--input-files`, pola L).

## 10. Testing (TDD wajib)

- Unit test driver: seed komposisi, done-rejection (belum ada PASS
  tersaksikan; diff kosong; diff file nyasar), pre-check pair, standar
  tunggal (fungsi evaluasi yang SAMA dipakai driver & gate), pesan
  penolakan English (pola test_rejection_messages_are_english).
- Unit test gate + eval gold (fixture diff sintetis).
- Drift-guard kontrak prompt bila memakai rule_catalog.
- `python -m pytest` hijau dari root main\ sebelum tiap commit.

## 11. Batas yang diketahui / non-goals

- Paket multi-file: tidak dibangun (data populasi 100% single-file).
- Special-casing repro yang lolos flip: SENGAJA bukan urusan product —
  ditangkap `fix_gold_eval` (dev realm).
- Base-FAIL tidak diverifikasi ulang di FIX (frozen yardstick sudah
  dibuktikan gate R; container deterministik dari image yang sama).
- Stage VERIFY: di luar scope spec ini (pola flip sudah jadi fisika FIX;
  bentuk VERIFY sebagai stage terpisah diputuskan nanti).
- Helper `apply_patch` (Prinsip Stabilisasi §2): belum dibutuhkan — model
  mengedit file langsung; dicatat sebagai lever bila kelas kegagalan
  mekanika edit muncul.
- Urutan kandidat = urutan tulis candidates.md (tanpa prioritas, keputusan
  LOCALIZE-tanpa-ranking); bukan `chosen` (advisory, sering lapisan simptom).
