# GEMMA-X: Gemma + harness open-source terbukti ("x") — pembanding eksternal pada set 46 case

**Date:** 2026-07-23 03:0x (WIB)
**Repo kerja BARU:** `/Users/mirza/Workspace/gemma-harness-swebench/gemma-x`
(project terpisah; JANGAN menyentuh `main/` kecuali entri katalog hasil)
**Referensi harness kita:** /Users/mirza/Workspace/gemma-harness-swebench/main (HEAD: 1fdc5fd)
**Dari → Ke:** claude-mac (sesi jaga-malam) → sesi BARU (Mac ini)
**Handoff saudara (matriks riset — jangan dicampur eksekusinya):**
- `.handoff/202607230245-prompt-gemma-baseline-ablasi-46-case.md` (Gemma polos)
- `.handoff/202607230230-prompt-claude-play-referensi-57-case.md` (Claude di 57 gagal)
**Perintah asal (Mirza, verbatim intent):** sama seperti gemma-baseline, tapi kali
ini Gemma dijalankan lewat **"x" = harness open-source TERKINI buatan orang lain
yang TERBUKTI handal di SWE-bench**. "x" dicari lewat **riset internet dulu**.
Project: `gemma-x`.

---

## 1. Tujuan & posisi di matriks riset

Melengkapi kuadran: (a) Gemma+harness-kita = 46/103; (b) Gemma polos = baseline
(handoff saudara); (c) Claude di 57 gagal = batas atas model; **(d) GEMMA-X =
Gemma + scaffold state-of-the-art eksternal** → menjawab: *apakah 46 kita bagus
karena harness kita, dan apakah plafon Gemma lebih tinggi di scaffold yang lebih
matang?* Jika x > kita di case tertentu → pelajari MEKANISME x di log-nya →
kandidat lever импор (dgn disiplin: serap KELAS mekanismenya, bukan tiru buta).
Jika kita > x di case tertentu → bukti nilai lever spesifik kita. **Log tetap
deliverable utama** (prinsip korpus komparatif).

## 2. LANGKAH 1 sesi baru: riset & pilih "x" (WAJIB verifikasi ulang di internet)

Shortlist hasil riset awal (2026-07-23, sesi lama — angka = SWE-bench Verified,
backbone Claude, sebagai bukti kematangan scaffold, BUKAN prediksi utk Gemma):

| Kandidat | Bukti kehandalan | Catatan kecocokan |
|---|---|---|
| **mini-SWE-agent** | 70,6% (Sonnet 4.5) | Paling sederhana (~ratusan baris), dukungan model lokal vLLM EKSPLISIT terdokumentasi (`hosted_vllm/<model>` + `api_base`); paling mudah diaudit log-nya |
| **SWE-agent** (Princeton) | 66,6% (Sonnet 4) | Dokumentasi "models & keys" dukung endpoint OpenAI-compatible/litellm penuh; ACI matang |
| **OpenHands** | 72,8% (Sonnet 4); proyek open-source paling aktif per 2026 | Fitur terbanyak; paling berat; litellm-based |
| **Live-SWE-agent** | 79,2% (Opus 4.5) — pemuncak scaffold OSS saat riset | Paling baru; VERIFIKASI dukungan endpoint custom & kematangan repo |
| Confucius CCA | 74,6% (Sonnet 4, paper) | Cek ketersediaan kode & kemudahan integrasi |

Sumber riset awal: leaderboard Live-SWE-agent (live-swe-agent.github.io),
Modal blog "Best Open Source Models for SWE-Bench Coding Agents 2026",
awesomeagents.ai leaderboard, dokumentasi swe-agent.com (installation/keys),
mini-swe-agent.com (local_models). VERIFIKASI ULANG semua (angka & dukungan
endpoint) — lanskap bergerak cepat.

**Kriteria pemilihan x (urut prioritas):**
1. **Dukungan endpoint OpenAI-compatible/vLLM kelas satu** (endpoint kita:
   `http://10.8.0.86:8000/v1`, model `gemma-4-31B-it`, vLLM) — tanpa fork besar.
2. Terbukti di leaderboard SWE-bench (Verified/full) & repo hidup (commit terkini).
3. **Log/trajectory lengkap & terstruktur** out-of-the-box (deliverable kita!).
4. Bisa dijalankan lokal per-case dgn image SWE-bench resmi (macOS/arm64+Rosetta,
   docker) — bukan hanya cloud.
5. Kesederhanaan audit (bila dua kandidat imbang, pilih yang lebih sederhana —
   rekomendasi awalku: **mini-SWE-agent** utk kecocokan vLLM + auditabilitas;
   naikkan ke SWE-agent/OpenHands bila butuh ACI lebih kaya. KEPUTUSAN FINAL:
   lapor hasil verifikasi ke Mirza dulu).

## 3. ATURAN MAIN gemma-x

1. **Harness x apa adanya** — konfigurasi default/rekomendasi resminya utk
   SWE-bench; JANGAN menambal x dgn lever kita (mencemari pembanding). Perubahan
   yang diizinkan HANYA: konfigurasi model/endpoint, budget, dan hook logging
   tambahan (read-only). Semua deviasi dari default WAJIB tercatat di README.
2. **Model & sampling sama**: Gemma `gemma-4-31B-it` @ `10.8.0.86:8000` (vLLM,
   OpenAI-compatible), **temp 0.0** (kalau x punya default sampling lain, catat
   dan samakan ke 0.0 demi paritas; kalau x BUTUH sampling>0 by design, konsultasi
   Mirza dulu).
3. **Aturan SWE-bench**: image resmi per case, `/testbed`, gold-blind (x tidak
   disuapi gold/test); wasit akhir = `swebench_eval` L2 yang SAMA dgn papan kita
   (jalankan dari tooling `main/` supaya angka sebanding — bukan skor
   self-reported x).
4. **Set case**: **46 case yang harness kita menang** (daftar §4) — simetris dgn
   gemma-baseline. Perluasan ke 57 gagal / 103 penuh = keputusan Mirza (§8).
5. **Log = deliverable**: simpan trajectory/log native x per run + normalisasi
   ringkas ke `console.log`-style bila format x eksotis; `meta.json` per run
   (case, versi x/commit-hash, config, turns/steps, biaya waktu). Artefak →
   `artifacts-gemma-x/` (luar git, konsisten kebijakan).
6. **Endpoint**: eksklusif Mirza, maks 7 lane total LINTAS project (memory
   `gemma-endpoint-parallel-lanes`) — koordinasikan bila baseline/harness lain
   sedang jalan; jangan tabrakan.

## 4. Daftar 46 case target (identik dgn gemma-baseline, per 2026-07-23 02:15)

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
Regenerasi (dari `main/`): `grep -l '"resolved": true' ../artifacts/f-dev/*/swebench_eval.json | sed -E 's|.*/f-dev--([^/]+)--r[0-9]+/.*|\1|' | sort -u`

## 5. Alur kerja yang kusarankan

1. **Riset & verifikasi x** (§2) → tulis `gemma-x/README.md` §"Pemilihan x"
   (kandidat, bukti, keputusan + alasan) → **lapor Mirza, minta ACC pilihan x.**
2. Install x di `gemma-x/` (venv/uv sendiri; JANGAN cemari venv main; dep via
   pyproject/lockfile x sendiri).
3. **Smoke 1-2 case kanari** (15347 / 11049 — image sudah ada): validasi
   end-to-end (x jalan dgn endpoint Gemma, log tersimpan, wasit kita membaca
   patch-nya). Ukur waktu/case & beban endpoint.
4. Lapor smoke ke Mirza → lampu hijau full-46.
5. Full-46 batch (paralel sesuai izin lane; rolling; pull image per batch
   `${c}":latest"` — awas zsh modifier; disk cek per batch, prune bekas).
6. **Papan 4-kolom** (`artifacts-gemma-x/papan-gemma-x.md` + gabung ke papan
   matriks): case × {harness-kita, baseline, gemma-x} → resolved + langkah/turn.
7. **Diagnosa komparatif** (protokol per-FAIL Mirza): (a) x MENANG di case yang
   kita menang → bandingkan efisiensi & jalur; (b) x GAGAL di case yang kita
   menang → mekanisme kita yang mana yang menyelamatkan (bukti nilai lever!);
   (c) temuan mekanisme x yang menarik → entri katalog
   `main/docs/katalog-lever.md` ("gemma-x <case>: ...", kandidat lever impor).
8. Commit rutin di repo gemma-x; entri katalog di main; push bila diminta.

## 6. Konteks & jebakan (dari sesi malam 23-jul)

- PASS harness kita 46/103 (papan `artifacts/papan-skor-retest-a0i-r20-mac.md`).
- Perilaku Gemma yang SUDAH kita tahu (relevan utk membaca log x): dialek
  `call:file:`/`<|tool_call>` (R20 kita menoleransi — x mungkin TIDAK; kalau x
  gagal parse aksi Gemma, itu DATA penting, catat kelasnya), loop repetisi
  (streak/periode-2/intra-reply), edit-mechanics (clobber/quicksand/no-op),
  fabrikasi output. Ekor `main/docs/katalog-lever.md` = peta lengkap.
- Endpoint vLLM: `curl -s http://10.8.0.86:8000/v1/models`; `max_model_len`
  262144. Format litellm utk vLLM: `hosted_vllm/<model>` + `api_base`.
- macOS arm64: image x86_64 jalan via Rosetta — lambat; jangan >5 container
  berat paralel tanpa cek beban.
- zsh: `${c}":latest"`; dep via pyproject (JANGAN pip ad-hoc — insiden venv
  22-23 jul: wasit L2 hilang senyap); `caffeinate` tak menahan clamshell sleep.
- Disk 231Gi bebas; ~30 image dari 46 belum ditarik (~2,2GB/image).

## 7. Definisi selesai

- README "Pemilihan x" + ACC Mirza.
- 46/46 run x tercatat (log native + meta + patch + swebench_eval dari wasit kita).
- Papan komparatif terisi + minimal 1 putaran diagnosa komparatif terkatalog.
- Tidak ada kontaminasi: papan rate utama & f-dev tak tersentuh.

## 8. Pertanyaan terbuka utk Mirza (tanyakan di awal)

1. ACC pilihan x setelah verifikasi (rekomendasi awal: mini-SWE-agent; alternatif
   OpenHands/SWE-agent/Live-SWE-agent)?
2. Budget langkah/turn x: default resmi x, atau paritas dgn harness kita (±60)?
3. Paralel berapa lane (endpoint bersama task lain)?
4. Setelah 46: lanjut ke 57 case gagal (ini justru paling menarik — apakah x
   memecahkan yang kita belum) / 103 penuh?
5. Urutan eksekusi antar-project (gemma-baseline dulu vs gemma-x dulu vs
   selang-seling)? Keduanya rebutan endpoint yang sama.
