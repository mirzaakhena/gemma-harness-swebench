# Adopsi Eksternal → Roadmap Lever (sintesis riset bot-05)

Dibuat 2026-07-22 (bot-04, sintesis dari `riset-komparatif-scaffold-swebench.md`
[bot-05]). Tujuan: memetakan temuan riset OSS ke **kelas kegagalan & lever kita**
([[taksonomi-kegagalan-per-fase]], [[rekomendasi-lever-dari-taksonomi]]) —
mana yang bisa DIPINJAM alih-alih dibangun dari nol. Status: **usulan analisa,
catat-only**; keputusan pemasangan = Mirza.

> **Terkait:** [[urutan-retest-lever]] (gelombang lever G2/G3) ·
> [[koreksi-hipotesis]] (disiplin verifikasi klaim riset)

## Peta: solusi eksternal → kelas/lever kita

| Sumber (lisensi) | Menyerang kelas/lever kita | Bentuk adopsi | Catatan |
|---|---|---|---|
| **Agentless** repro-gen (MIT) — sample ~40 kandidat repro, filter eksekusi "Issue reproduced", majority-vote | **§R REPRODUCE-wall (dominan, 20/103)** — pengganti/pelengkap rerun-r1→r3 kita | sample-banyak + filter-eksekusi + vote kanonik, gold-blind | **⚠ tension:** sampling butuh temp>0 (diversitas); Mirza sudah TOLAK seeded-temp demi reproducibility (R9-opt-b). Perlu keputusan: reproducibility vs diversitas sampling. |
| **Agentless** localize 3-tahap hierarkis (MIT) | **§L Kelas-A recall-miss** (6 case sejati) — bucket tanpa-obat terbesar kita | file→skeleton→baris, non-agentic, gold-blind | Cocok filosofi non-agentic kita; kandidat lever recall-L yang selama ini buntu (larangan cek-gold). |
| **TestPrune** (Okt-2025, lisensi?) — minimisasi regression-suite, +8-13% resolve di Agentless | **§F-2 over-broad → P2P regresi** (5 case: 11999/12907/15400/11910/12284) + gap "gate tak jalankan P2P" (11910) | subset P2P efisien → gate FIX bisa jalankan sebagian P2P tanpa ongkos penuh | Menjawab kandidat lever yang tertunda: "gate jalankan sebagian P2P". Preprint. |
| **EvoOtter** (IBM, preprint Jul-2026) — nilai kualitas repro TANPA gold via rule-based mutant + full-log-diff | **§F K4 (kontrol-positif absen, 45/52)** — R14 kita (CONTROL-MARKER) | mutation-testing sbg pengukur kualitas repro, komplemen flip-test | Preseden gold-blind TERKUAT yang ditemukan; teknik yang KITA BELUM PUNYA. Klaim performa-nya sudah DITOLAK verifikasi — pakai konsepnya, bukan angkanya. |
| **mini-SWE-agent** (referensi resmi leaderboard; "no tool-calling API, bash saja") | **§R-1/R-2 token-loop degeneratif** (keluarga KH-12, 5 case wall) + R5/R9 kita | hindari tool-calling API sepenuhnya → mungkin sidestep `<\|tool_call\|>` degenerate | **BELUM terverifikasi** (kalah budget-cut riset). Kandidat riset-lanjutan PALING relevan ke masalah terberat kita. |
| **SWT-Bench** flip-test formal (NeurIPS'24) | **§V VERIFY kita** | — (validasi, bukan adopsi) | Flip-test kita identik-struktural dgn definisi baku → desain VERIFY kita SEHAT. Tak perlu aksi. |

## Temuan strategis inti (untuk Mirza)

1. **Desain kita = KOMBINASI NOVEL, bukan komponen novel.** Tiap elemen (self-written
   repro, gold-blindness ketat, flip-test formal) SUDAH ada terpisah di OSS; yang
   tak ada preseden = menggabungkan ketiganya dalam satu pipeline HIDUP + phase-gating
   ketat. **Konsekuensi:** kita tak buang-buang tenaga (kombinasinya baru), TAPI bisa
   MEMPERCEPAT dengan meminjam komponen matang alih-alih menemukan ulang.

2. **3 pinjaman berdampak-tinggi, terurut leverage:**
   - **(a) Agentless repro-gen** → menyerang REPRODUCE-wall (kelas kegagalan #1 kita).
     Potensi terbesar, tapi bentrok reproducibility — keputusan Mirza dulu.
   - **(b) TestPrune** → mengaktifkan "gate jalankan sebagian P2P" (menutup F-2/11910
     yang gate kita by-design tak bisa tangkap). Konkret, terukur (+8-13%).
   - **(c) EvoOtter mutation-quality** → isi baru untuk R14 (kualitas repro tanpa gold).

3. **Riset-lanjutan WAJIB (celah nyata, 0 klaim terverifikasi):** sub-problem 4
   (robustness tool-call — masalah TERBERAT kita), 5 (orkestrasi runtime — R13),
   6 (scaffold model-lemah — pertanyaan asli Mirza, belum terjawab). Target prioritas:
   **mini-SWE-agent** (relevan langsung ke token-loop), lalu OpenHands/SWE-ReX (runtime),
   + 4 kandidat awal Mirza yang tak tersentuh (Moatless/Aider/OpenHands/RepoUnderstander).

## Relasi ke gelombang lever

- Tidak mengubah G1 (sudah terpasang) maupun keputusan "G2 setelah baseline valid".
- **Menambah kandidat untuk G2/G3 & seterusnya:** Agentless-repro-gen dan
  Agentless-localize berpotensi lebih tinggi-leverage daripada beberapa lever internal
  kita (mis. keduanya menyerang dua bucket terbesar: REPRODUCE-wall & Kelas-A recall).
  Layak dipertimbangkan Mirza saat menyusun isi G2/G3.
- Semua preprint → **cek lisensi per-repo sebelum pinjam kode** (hanya Agentless
  terkonfirmasi MIT).

*Catat-only. Aksi berikutnya (kalau Mirza mau): (1) putuskan tension reproducibility
vs Agentless-sampling; (2) riset-lanjutan mini-SWE-agent (utus bot-05 lagi);
(3) baca kode Agentless repro-gen + TestPrune untuk spec adopsi konkret.*
