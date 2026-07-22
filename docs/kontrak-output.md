# Kontrak Output Seragam — schema_version 1.0.0

Sumber kebenaran teknis untuk SEMUA output run. Konsumen utama: dashboard
rlfv-monitor (bot-03, adapter-per-format). Versi vault: design doc §3 +
"Kebutuhan konsumen dashboard untuk kontrak output (bot-03)".

**Emitter tunggal:** `harness/emit.py` — satu-satunya modul yang boleh menulis
file-file di bawah. Kontrak dijaga di satu titik, teruji unit.

> **Terkait:** [[prinsip-pengembangan]] (arah proyek) · [[sop-rlfv-case-run]]
> (cara pakai) · [[2026-07-20-swebench-checker-l2-design]] (checker L2) ·
> [[2026-07-20-fix-stage-design]] (stage FIX)

## 1. Layout artifacts

```
artifacts\<campaign>\
├── campaign.json               ← snapshot katalog saat kampanye dibuat (atomic)
├── runs.jsonl                  ← indeks kampanye: 1 baris per run start/end
└── <run_id>\
    ├── events.jsonl            ← stream event live (append-only)
    ├── verdict.json            ← hasil final, ATOMIC (temp → os.replace)
    ├── console.log
    └── files\                  ← artefak fase: repro.md, localize.md,
                                   fix.diff, fix.md, verify.md
```

- `run_id` = `<campaign>--<case_id>--r<N>`; `case_id` PENUH
  (mis. `django__django-11910`) — short numerik DILARANG jadi join key.
- Rerun = `r<N+1>` = direktori BARU; dir lama tidak pernah dimutasi/dihapus
  (append-only; purge hanya via graveyard).
- Satu file = satu penulis. Dashboard cukup watch mtime `runs.jsonl`.
- Nama file SERAGAM lintas kampanye (tidak ada progress file variatif).

## 2. Encoding (WAJIB, di-enforce emitter)

UTF-8 **tanpa BOM**, newline **LF** (`open(..., encoding="utf-8", newline="\n")`).
JSONL = satu baris satu objek; byte `\r` di file adalah BUG (insiden nyata:
15 event hilang karena `\r` nyasar di tengah token).

## 3. Event — satu baris `events.jsonl`

```json
{"schema_version":"1.0.0","ts":"2026-07-18T14:03:22+07:00",
 "run_id":"r-dev--django__django-11910--r1","case_id":"django__django-11910",
 "campaign":"r-dev","phase":"reproduce","event":"enter",
 "verdict":null,"attempt":1,
 "budget":{"msg_used":12,"msg_limit":60},
 "counters":{"fix_tries":null,"loc_tries":null,"stage_call":null},
 "detail":{}}
```

- `phase` ∈ `reproduce | localize | fix | verify`
- `event` ∈ `enter | exit | retry | skip | abort`
- `verdict` terisi HANYA saat `exit` (null selain itu).
- `attempt` mulai 1. `budget` = `{msg_used, msg_limit}` (boleh null).
- `counters` = `{fix_tries, loc_tries, stage_call}` — standar, boleh null;
  BUKAN dikubur di `detail`.
- `detail` = object bebas per fase. Kunci terstandar: `detail.sub_stage` ∈
  `investigate | survey | select`; abort → `detail.reason`.
- Retry/eskalasi = event terstruktur (`event:"retry"`), bukan baris teks bebas.
- Timestamp ISO8601 dengan offset — `enter`/`exit` per fase ⇒ durasi per-fase
  tersedia native.

## 4. Enum verdict (TERTUTUP per fase)

- `reproduce` / `localize` / `verify`:
  `pass | fail | syntax-fail | wrong-logic | timeout | abort`
- `fix`: `flip | no-flip | empty-patch | timeout | abort`

Aturan evolusi: TAMBAH nilai baru → naikkan schema_version **minor**;
DILARANG mengganti makna nilai lama. Dashboard toleran string asing
(render apa adanya) tapi mapping warna butuh enum stabil.

## 5. `verdict.json` (final, atomic)

```json
{"schema_version":"1.0.0","run_id":"...","case_id":"...","campaign":"...",
 "phases":{"reproduce":{"verdict":"pass","duration_s":312},
           "localize":{"verdict":"pass","duration_s":190},
           "fix":{"verdict":"flip","duration_s":845},
           "verify":{"verdict":"pass","duration_s":120}},
 "wall":null,"pass_l1":true,"pass_l2":true,
 "started":"...","finished":"...","files":"files/"}
```

- `phases` boleh berisi subset (kampanye per-fase, mis. REPRODUCE-only →
  hanya kunci `reproduce`).
- `wall` = fase tempat run mentok (`reproduce|localize|fix|verify`) atau
  `"abort"` atau `null` (tidak mentok).
- `pass_l1` = vonis mekanis gold-free; `pass_l2` = skor resmi swe_bench;
  keduanya boleh null bila belum dinilai.
- Ditulis SEKALI di akhir run: temp file → `os.replace` (atomic).

## 6. `runs.jsonl` (indeks kampanye)

```json
{"schema_version":"1.0.0","ts":"...","run_id":"...","case_id":"...",
 "campaign":"...","event":"start"}
{"schema_version":"1.0.0","ts":"...","run_id":"...","case_id":"...",
 "campaign":"...","event":"end","verdict":{...ringkas per fase...},"wall":null}
```

Baris `end` membawa `verdict` (map fase→verdict) + `wall`.

## 7. `campaign.json` (snapshot katalog)

```json
{"schema_version":"1.0.0","name":"r-dev","created":"...",
 "description":"Fase REPRODUCE — dev loop frontier vs Gemma",
 "cases":[{"case_id":"django__django-11910","tier":"B1","dev_set":true}]}
```

Snapshot BEKU saat kampanye dibuat — dashboard tidak pernah menyentuh git
tree; kebal edit katalog di tengah kampanye; pending cases kelihatan.

## 8. Semantik crash/kill

Runner wrapper memasang trap → sebisanya emit event
`{"event":"abort","detail":{"reason":...}}` + `verdict.json` dengan
`wall:"abort"`. Dashboard SAH menandai run *stalled* bila `events.jsonl` tak
bertambah > N menit tanpa `verdict.json` (N default 10).

## 9. Gate fase REPRODUCE (dari P25 Divergence Retrospective)

Sebelum artefak `repro.md` boleh membawa `CONFIRMED-AT-BASE: yes` (dan fase
diberi verdict `pass`), HARNESS memverifikasi mekanis:

1. **Anti-vacuous:** repro FAIL di HEAD dengan gejala yang DIKUTIP issue;
   `expected == observed` di HEAD → TOLAK (bukan repro, cuma deskripsi).
2. **Self-contained:** system re-run REPRO COMMAND di sandbox segar; error
   yang berakar di scaffolding (ModuleNotFoundError, settings) → TOLAK.
3. **Idempoten:** system run 2× dari state bersih; output wajib identik
   (repro stateful → sinyal flip tak terbaca di fase FIX).
4. **Predikat = keluhan user:** EXPECTED menguji observable yang dikutip
   issue (output/exit code), BUKAN proxy interpretasi penyebab. (Kasus nyata:
   predikat `type(value) is str` yang gold patch pun tak penuhi — 11964.)

Rasional lengkap: vault `P25 — Divergence Retrospective — Hasil` §4 Paket 1.

## 10. Artefak fase (simetri 4 fase)

| Fase | Artefak wajib di `files/` | Isi inti |
|---|---|---|
| R | `repro.md` (+ script repro) | 5 slot (3 interpretif + 2 mekanis), SATU varian parser |
| L | `localize.md` | SATU format slot `chosen/file/lines/what/why/evidence`; jalur fallback pun wajib emit `chosen` |
| F | `fix.diff` + `fix.md` | tracked diff (file BARU via `git add -N`) + telemetri ronde/detector |
| V | `verify.md` | verdict + alasan klasifikasi + potongan bukti |
