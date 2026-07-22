# Analisis Konsep Split FIX/VERIFY — Sinkronisasi UI ↔ Runner

**Dibuat:** 2026-07-22 (tanggapan bot atas definisi konsep Mirza, sesi ngobrol
pasca-riset). **Status:** analisis + hasil pengecekan kode, catat-only —
keputusan desain tersisa ada di §6.

> **Terkait:** [[riset-split-tab-fix-verify]] (riset effort/opsi yang
> ditanggapi) · [[api-ui-viewer]] (kontrak API yang terdampak) ·
> [[kontrak-output]] (skema artefak product realm)

## 1. Konteks — definisi konsep dari Mirza

Mirza mendefinisikan ulang makna dua tab yang diminta:

- **FIX** = usaha model memperbaiki kode + testing mandiri dengan `repro.py`,
  mendeklarasi PASS/FAIL secara sepihak. Jika `repro.py` bilang PASS, status
  yang tampil benar-benar PASS. FIX itu **gold-blind**.
- **VERIFY** = testing memakai **official SWE-bench checker** sebagai juri
  akhir yang memutuskan apakah vonis tahap FIX benar-benar lulus.
- **Dampak pemisahan:** tidak ada lagi status WAIT.

Dokumen ini memvalidasi konsep itu terhadap kode runner dan UI, satu per satu.

## 2. Konsep FIX — valid, dengan satu penajaman

Kata "sepihak" perlu dipertajam: yang PASS **bukan klaim mentah model**.
Alur di `harness/stages/run_fix_gates.py` + `harness/stages/fix_gates.py`:

1. Model mendeklarasi DONE.
2. **Harness yang menyaksikan**: patch di-apply ke dunia segar, dicek hanya
   menyentuh file kandidat, lalu `repro.py` beku (hasil stage REPRODUCE)
   dijalankan **2× di container segar** — keduanya wajib mencetak
   `REPRO_STATUS: PASS` baris-eksak (`fix_gates.py:101`).

Jadi "sepihak" dalam arti **gold-blind dan self-contained** (jurinya
`repro.py` buatan model sendiri, tanpa gold patch/test resmi) — tapi bukan
self-reported; harness yang mengeksekusi vonisnya.

> [!important] Temuan sinkronisasi kunci
> `run_fix_gates.py:55` menulis `pass_l1=(verdict == "flip")` —
> **pass_l1 dan flip identik secara definisi di sisi runner**. Ekspresi UI
> `product_pass = flip AND pass_l1` (`ui/server.py:403`) redundan-defensif,
> bukan dua kondisi berbeda. Definisi tab FIX = "flip" saja sudah lengkap
> dan sinkron.

## 3. Konsep VERIFY — valid, plus satu properti penting

`eval/swebench_checker.py`: ambil `files/fix.diff` → apply ke container
Epoch segar → apply `test_patch` resmi → jalankan test resmi → grade →
`swebench_eval.json` dengan `resolved` sebagai vonis juri akhir. Semua nama
field yang dibaca UI (`resolved`, `f2p_failed`, `p2p_failed`,
`patch_successfully_applied` di `ui/server.py:408-414`) sinkron dengan yang
ditulis checker.

Properti penting: **checker hanya butuh `fix.diff`** — tidak peduli L1 pass
atau tidak. Di tab VERIFY, run yang FIX-nya FAIL pun sah punya vonis L2
sendiri. VERIFY benar-benar juri independen, bukan lanjutan FIX.

## 4. Dampak "tidak ada lagi WAIT" — benar di FIX, ada keputusan tersisa di VERIFY

**Tab FIX:** WAIT hilang alami. WAIT hari ini = "product_pass tapi checker
belum jalan" (`ui/server.py:418-421`) — sinyal lintas-lapisan; dalam kacamata
FIX murni, baris itu memang sudah PASS penuh.

**Tab VERIFY:** masih ada satu keputusan — baris tanpa `swebench_eval.json`
statusnya apa? Kandidat alami: `?` ("belum dinilai juri"). Secara semantik
memang bukan WAIT lagi (WAIT mengandung asumsi "menunggu sesuatu yang pasti
datang"; `?` netral).

> [!warning] Ambiguitas dari sisi runner
> Checker **sengaja TIDAK menulis** `swebench_eval.json` saat infra error
> (docker gagal/timeout — `swebench_checker.py:94,179`), supaya error infra
> tidak jadi vonis palsu. Konsekuensi: "file absen" punya dua makna —
> *belum pernah dijalankan* ATAU *dijalankan tapi crash infra* — dan UI
> tidak bisa membedakannya dari artefak. Hari ini keduanya jatuh ke WAIT;
> setelah split keduanya jatuh ke `?`. Kalau pembedaan ini penting, checker
> perlu mulai menulis artefak error — perubahan kecil tapi menyentuh sisi
> runner, bukan UI saja.

Yang ikut hilang bersama WAIT: **ANOMALY** (L1 FAIL tapi `resolved=True`,
`ui/server.py:422-426`). Dengan split, dia terurai jadi FAIL di tab FIX +
PASS di tab VERIFY — kontradiksinya hanya terlihat bila orang membandingkan
dua tab. Riset menyarankan badge kecil; alternatif: direlakan hilang total.
Keputusan Mirza.

## 5. Hasil pengecekan sinkronisasi UI ↔ runner

| Titik | Runner menulis | UI membaca | Status |
|---|---|---|---|
| `pass_l1` | `run_fix_gates.py:55`: `pass_l1=(verdict=="flip")` | `ui/server.py:403`: `flip AND pass_l1` | ✅ sinkron (UI redundan-defensif) |
| abort path | `run_fix_gemma.py:186`: `phases={}, pass_l1=None` | jatuh ke alur lama → FAIL | ✅ sinkron |
| `swebench_eval.json` | checker: `resolved`, `f2p_failed`, `p2p_failed`, `patch_successfully_applied` | `ui/server.py:400-414` baca field yang sama | ✅ sinkron |
| infra error checker | **tidak menulis apa pun** (sengaja) | absen → WAIT (tak bisa bedakan "belum jalan" vs "crash") | ⚠️ ambigu — relevan buat desain `?` di tab VERIFY |
| L1-fail + belum dicek | tidak ada `swebench_eval.json` | `_fix_verify_status` return `None` → FAIL (alasan product) | ⚠️ di tab VERIFY mandiri harus jadi `?`, bukan FAIL warisan L1 |

Dua baris terakhir = PR desain yang tersisa; sisanya bersih.

## 6. Dua realm: "harness development" vs "harness as a product"

- **Harness as a product** = pipeline yang dikirim: stage reproduce →
  localize → fix (→ verify masa depan), berjalan **gold-blind**, menulis
  artefak kontrak (`verdict.json`, `pass_l1`, dst per [[kontrak-output]]).
  Realm ini dilarang import dari `eval/` — ada duplikasi kode yang disengaja
  demi itu (`fix_gates.py:22-24`).
- **Harness development** = meta-lapisan Mirza untuk mengukur produk itu:
  `eval/` (gold eval, swebench_checker), dashboard `ui/`. Realm ini **boleh**
  melihat gold dan test resmi karena menghakimi produk dari luar.
  `swebench_eval.json` eksplisit file realm dev, bukan artefak kontrak.

> [!tip] Argumen terkuat untuk split — lebih kuat dari "biar enak dibaca"
> **Tab FIX = apa kata produk tentang dirinya sendiri (gold-blind); tab
> VERIFY = apa kata juri eksternal (realm dev).** Split tab jadi cermin 1:1
> dari batas realm yang memang sudah ada di arsitektur. Justru status
> gabungan hari ini yang mencampur dua realm dalam satu kolom.

Framing ini juga menjelaskan kenapa tabrakan nama "VERIFY"
([[riset-split-tab-fix-verify]] §5.2) nyata: phase `"verify"` yang
direservasi di `harness/emit.py:17` adalah VERIFY **realm produk** masa
depan, sedangkan tab VERIFY yang diminta sekarang adalah penghakiman
**realm dev**. Dua realm, satu nama. Kalau framing "tab = realm" diterima,
nama tab yang jujur bisa jadi "VERIFY (SWE-bench)" atau "JUDGE" — obrolan
lanjutan.

## 7. Kesimpulan & keputusan tersisa

Konsep Mirza valid dan kode sudah sinkron untuk menopangnya. Yang tersisa
murni keputusan desain:

1. **Representasi "belum dicek" di tab VERIFY** — `?` polos, atau bedakan
   "belum jalan" vs "crash infra" (butuh checker menulis artefak error).
2. **Nasib ANOMALY** — hilang total, atau badge lintas-lapisan kecil.
3. **Nama tab** — terima risiko pemakaian ulang nama "VERIFY", atau amankan
   dengan nama lain untuk checker L2 sekarang.
