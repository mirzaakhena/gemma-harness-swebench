# Audit Integritas Data — Cases Sudah-Selesai (fan-out Haiku)

**Dibuat:** 2026-07-21 (bot-03, permintaan Mirza). **Metode:** 5 subagent Haiku paralel, read-only, audit **95 case** yang punya run r-dev (=sudah dijalankan). Tiap case dicek 5 sinyal "label-yang-bohong" / cacat data, verifikasi ke artefak (bukan label mentah). **Status: catat-only untuk di-revisit Mirza.**

> **Terkait:** [[koreksi-hipotesis]] (KH-16/KH-17 — akar temuan) ·
> [[rekomendasi-lever-dari-taksonomi]] (R18/R19 = KL-G3-1/2) ·
> [[taksonomi-kegagalan-per-fase]] (kelas R-8 corrupt-gold) ·
> [[sop-rlfv-case-run]] (§3b sabotase utk kandidat lulus-palsu)

**Konsistensi:** temuan corrupt-patch Haiku (4 completed) COCOK dengan scan statis independen bot-03 `git apply --numstat` seluruh 97 gold.patch (5 corrupt; 15202 excluded dari audit ini karena belum-run/grup-4). Kecocokan dua metode = sinyal keyakinan.

---

## Ringkasan temuan (14 case ber-flag / 95; ~81 bersih)

### 1. Corrupt gold.patch → verdict `wrong-logic` MISLABEL (akar-DATA, bukan model) — 4
`git apply gold.patch` gagal parse ("corrupt patch at line N") → flip test short-circuit → repro tak jalan di gold-world → mislabel `wrong-logic`. Base repro JALAN benar.
- `django__django-12184` (@14), `django__django-12856` (@15), `django__django-13321` (@19), `django__django-14155` (@22).
- (`django__django-15202` @41 juga corrupt tapi belum-run; sedang di grup-4.)
- **Total korpus: 5/97 gold.patch corrupt.** Lihat KH-16, kandidat KL-G3-1 (validasi `git apply --check` saat prepare_cases).

### 2. `syntax-fail` MISLABEL — verdict syntax-fail TAPI tak ada repro.py (artifacts-missing / no-fence KH-12, BUKAN SyntaxError asli) — 5
`files/` cuma berisi `pipe_runtime.py`; model emit `<|tool_call>` tanpa fence → 0 aksi → repro tak pernah ter-persist. Verdict `syntax-fail` = mislabel "artifacts missing".
- `django__django-13265`, `django__django-14411`, `django__django-14855`, `django__django-15851`, `django__django-15902`.
- Konsisten temuan bot-04 (taksonomi: syntax-fail = 100% artifacts-missing di korpus, 0 SyntaxError asli). Keluarga KH-12.

### 3. FALSE-PRUNE — `file_match=false` TAPI `qualified=true` (gold ADA di shortlist, tapi prune akan skip) — 3
Prune (`should_prune_fix`) keying `file_match` (pointed primer), sedang qualify/FIX-iterasi keying `qualified` (any-shortlist ∈ gold) → inkonsisten.
- `django__django-13033` (grup-3, sudah kena prune nyata), `django__django-11620`, `django__django-11742` (label "Kelas-A" tercemar — qualified=true berarti recall sukses).
- Lihat KH-17, kandidat KL-G3-2 (prune keying `qualified`).

### 4. LULUS-PALSU KANDIDAT — `resolved=true` TAPI `file_match=false` (test resmi lolos, patch di file non-gold) — 2
⚠️ **KANDIDAT, belum dikonfirmasi.** Perlu §3b sabotase untuk pisahkan **lulus-palsu-sejati** vs **fix-alternatif-lokasi-valid** (SOP §3b, preseden 13658/11620).
- `django__django-11620` (known — instans ke-2 pasca 13658; juga false-prune), `django__django-11964` (**BARU** — belum pernah di-flag; prioritas §3b).

### 5. MISSING `swebench_spec.json` — VERIFY ke-blok diam (resolved=None WAIT) — 2
Case dir cuma `gold.json` + `gold.patch`, spec absen → `swebench_checker` gagal "spec not found" → nyangkut.
- `django__django-11905`, `django__django-14667`.
- Fix murah: re-fetch spec via `fetch_swebench_spec` (preseden commit 69bf27d bot-04 utk 11797/13158/15320).

---

## Per-slice (mentah, dari 5 Haiku agent)

- **Slice 1 (19: astropy×6 + django 10914–11583):** SEMUA BERSIH (0 flag). Catatan: 10924/11564 r3-`wrong-logic` = genuine won't-flip (bukan corrupt; 11564 = KH-15 App-API/judge).
- **Slice 2 (19: 11620–12497):** 12184 corrupt-victim; 11620 false-prune+lulus-palsu; 11742 false-prune; 11905 missing-spec; 11964 lulus-palsu. (14 bersih.)
- **Slice 3 (19: 12589–13448):** 12856 + 13321 corrupt-victim; 13265 syntax-fail-mislabel; 13033 false-prune. (15 bersih.)
- **Slice 4 (19: 13551–14672):** 14155 corrupt-victim; 14411 syntax-fail-mislabel; 14667 missing-spec. (16 bersih.)
- **Slice 5 (19: 14752–15902):** 14855 + 15851 + 15902 syntax-fail-mislabel. (16 bersih.)

## Rekomendasi tindak-lanjut (untuk revisit Mirza)
1. **Fix 5 corrupt gold.patch** (12184, 12856, 13321, 14155, 15202) + re-run — sudah di-approve Mirza (re-run semua 5).
2. **§3b sabotase** utk 2 lulus-palsu-kandidat (11620, 11964) — pisahkan false-pass vs alt-valid.
3. **Re-fetch spec** utk 11905, 14667 (murah).
4. **Terapkan KL-G3-1/KL-G3-2** (validasi gold.patch setup; prune keying qualified) — cegah kelas ini berulang.
5. 5 syntax-fail-mislabel = keluarga KH-12 (label→identifikasi-gejala, sudah kandidat bot-04) — bukan aksi baru.
