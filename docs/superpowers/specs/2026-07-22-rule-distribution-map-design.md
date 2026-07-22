# Peta Distribusi Rule — desain (2026-07-22)

**Oleh:** bot-06 · **Untuk:** Mirza · **Status:** disetujui (Telegram, 2026-07-22)

> **Terkait:** [[katalog-lever]] (sumber lever) · [[prinsip-pengembangan]]
> (higiene prompt §4b — konteks rule)

## Tujuan

Melihat mana rule/lever/mekanik yang **dipakai umum** vs **dipakai khusus untuk
case tertentu**, supaya bisa memprioritaskan mana yang harus dipertahankan atau
diperkuat. Wujud: tab baru "Distribusi" di app `ui/rule-map/index.html`.

## Dua sumbu

1. **Origin breadth (kolom) — dari data, jujur.** Dihitung mekanis dari
   `origin.case_ids` tiap rule:
   - `Fondasi` = 0 case (keputusan desain fundamental)
   - `Single` = 1 case
   - `Few` = 2–3 case
   - `Broad` = 4+ case
   Caveat jujur: sebagian entri `case_ids` adalah rerun-id (`r9`, `r12`), bukan
   case SWE-bench unik; breadth = jumlah entri mentah. Belum di-dedupe (Mirza
   memilih "Setuju, lanjut", bukan opsi dedupe — bisa dirapikan kalau perlu).

2. **Runtime scope (baris) — klasifikasi bot-06, ditandai subjektif.** Diturunkan
   dari membaca `what`+`name` tiap rule, disimpan di sidecar
   `ui/rule-map/scope-annotations.json` (bukan mengubah `rule-inventory.json`
   milik bot-04). Nilai:
   - `always-on` — jalan tiap run/DONE/attempt di fase-nya, tanpa syarat kasus
     (gate, guard, compose, evaluator, single-writer).
   - `conditional` — jalan tiap run tapi hanya **bertindak** saat detektor/sinyal
     runtime menyala (stall, timeout, marker bentuk, mixed-block, first-fail).
   - `targeted` — hanya kepakai untuk **kelas kasus** tertentu (server/app, probe
     ber-Model, one-shot, log non-ASCII).
   Tiap rule diberi 1 baris `reason` agar owner bisa mengoreksi.

## Tier prioritas (overlay warna sel)

Ditentukan oleh dua ambang: scope (`always-on` vs bukan) × breadth (`>=2` vs `<=1`).

| tier | kombinasi | arti |
|------|-----------|------|
| 🟥 p1 Pertahankan & perkuat | always-on × breadth≥2 | load-bearing, banyak case gantung di sini |
| 🟧 p2 Fondasi struktural    | always-on × breadth≤1 | tulang punggung desain, jaga tetap utuh |
| 🟨 p3 Bertarget tapi terbukti | (conditional/targeted) × breadth≥2 | kandidat diperkuat |
| ⬜ p4 Niche / review        | (conditional/targeted) × breadth≤1 | review, apalagi kalau roadmap / ber-marker gugur |

## Bentuk & interaksi

- **Matrix 3×4** (baris scope × kolom breadth), bukan scatter — bucket diskret,
  scatter = presisi palsu. Tiap sel: jumlah rule + jumlah roadmap + ikon tier +
  flag ⚑ bila ada rule ber-marker kurator. Sel diwarnai per tier.
- **Klik sel** → daftar rule di bawah ke-filter ke sel itu. Klik kartu → drawer
  detail (reuse dari Peta Fase) + section baru "Klasifikasi distribusi"
  (breadth, scope, tier, alasan scope).
- Matrix menghormati filter atas (status/layer/marker/search). Default status
  `terpasang` → melihat distribusi yang benar-benar aktif; toggle `Semua` untuk
  termasuk roadmap.

## Hasil distribusi (status=Semua, 70 rule)

- scope: 48 always-on · 14 conditional · 8 targeted
- breadth: 31 Fondasi · 22 Single · 13 Few · 4 Broad
- tier: **11 p1** · **37 p2** · **6 p3** · **16 p4**

## Batas & kejujuran

- Sumbu breadth 100% dari data; sumbu runtime-scope adalah judgment bot-06
  (ditandai di UI + `reason` per rule).
- "terpasang" tetap berarti kode hijau, bukan "terbukti menaikkan PASS"
  (disclaimer honesty kurator tetap tampil).
- `docs/rule-inventory.json` tidak diubah; semua tambahan disjoint
  (`ui/rule-map/index.html`, `ui/rule-map/scope-annotations.json`).
