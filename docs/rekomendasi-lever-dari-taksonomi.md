# Rekomendasi Lever dari Taksonomi Kegagalan — mekanis & prompt, ter-prioritas

Dibuat 2026-07-21 (bot-04, Fable 5). Plane: SMARTXRESE-398 (permintaan Mirza,
lanjutan SMARTXRESE-397 [[taksonomi-kegagalan-per-fase]]).

**Status (update 2026-07-22): GELOMBANG 1 DITERAPKAN — 9 lever, GO Mirza,
TDD, pytest 465 hijau, satu commit per lever:**
R19 `0d835b6` · R1 `0444b81` (bot-04) · R2 `8933a06` · R3 `d592ccc` ·
R4 `8aac0d0` · R5 `d4c455b` (`no_progress.py`, trigger #1/#2/#8, K=3/X=15,
inject-unik→break) · R6 `6aff344` · R7 `2279cbc` · R18 `84c70e8` (bot-02).
Status DITERAPKAN + tabel hash juga tercatat di [[katalog-lever]] (`3faf24e`).
**Gelombang 2/3 (R8–R17) tetap CATAT-ONLY** sampai instruksi Mirza berikutnya.
Nomor LV-xx merujuk [[katalog-lever]]; kelas R-x/L-x/F-x/V-x/H-x merujuk
[[taksonomi-kegagalan-per-fase]].

> **Terkait:** [[urutan-retest-lever]] (urutan validasi R1–R19) ·
> [[adopsi-eksternal-dari-riset]] (komponen OSS yang bisa dipinjam) ·
> [[koreksi-hipotesis]] (KH yang jadi basis bukti) ·
> [[audit-integritas-cases-selesai]] (asal R18/R19)

**Basis bukti (tiga sumber, dua di antaranya via subagent ber-izin-membantah):**
1. Taksonomi per-fase + sweep mekanis seluruh artefak (220 r-dev / 135 l-dev / 66 f-dev).
2. Pembacaan kode harness — semua anchor `file:line` di bawah diverifikasi langsung ke
   kode 2026-07-21 (subagent kode; dua koreksi pentingnya dicatat di §5).
3. Sweep vault (`C:\Users\Mirza\mirza-vault\Projects\SWE-bench Gemma Harness\`) —
   angka atribusi historis + lesson yang belum semua tercatat di docs/ (subagent vault).

---

## §0 — Prinsip seleksi (kenapa urutannya begini)

Angka historis proyek sendiri (vault) yang jadi dasar bobot:

- **Lever MEKANIS 100% vs rule prompt pasif 17%**: L-a (validasi rentang mekanis)
  12747 0/3→3/3; R-a (rule prompt observable-behavior) 11905 0/3→0/3 — rule diabaikan
  3/3; R-b 1/3 patuh. (R-dev Log, "paket hampir-pasti".)
- **Nuansa yang menyelamatkan prompt dari vonis mati:** rule prompt NEMPEL bila hanya
  mengubah *cara model menurunkan literal* (Paket Predikat: 11797 & 13220 0/3→3/3),
  GAGAL bila menuntut model *menambah mekanisme asing* (warnings-capture, settings).
- **Tangga enforcement 4 tingkat** (vault, Asal-usul Rule & Lever): by-construction →
  gate mekanis → injeksi ber-sinyal → prompt CORE. Prompt = opsi terakhir; aturan
  tanpa sinyal mekanis tidak boleh injeksi-only.
- **Filter frontier-baseline** sebelum invest lever pada kelas deterministik: kalau
  frontier dengan input PERSIS sama juga gagal (14667), kelasnya noise sah — jangan
  dilever. Kalau frontier flip (11905, 13768), resep frontier = spesifikasi lever.
- **Lever bisa kondisional-wajib:** uplift2 era lama unlock 2 case sambil merusak 2
  case lain. Lever baru diuji jangan hanya pada kelas targetnya.
- **Wasit evaluasi lever = checker L2**, bukan repro-flip (P23: L1 25/52 vs L2 6/52;
  false-success 20). Dan kontrol budget saat mengklaim lift (lesson uplift2).

---

## §1 — TIER 1: mekanis, kecil, dampak langsung (quick wins)

### R1. Tutup LV-09: kirim `pipe_runtime.py` ke dunia kerja FIX (+ gap kembar di LOCALIZE)

- **Menyerang:** F-4 FIX-no-flip (4 case; 3 di antaranya ber-`No module named
  'pipe_runtime'` 441/588/232 kejadian) + pembakaran turn di 10 run/8 case f-dev.
- **Kode:** `run_fix_gemma.py:231-232` hanya menulis `repro.py`; pembanding R-driver
  `run_reproduce_gemma.py:286-290`; dunia segar sudah benar
  (`repro_sandbox_runner.py:34-36` copy kondisional). **Gap kembar:**
  `run_localize_gemma.py:180` juga tidak mengirim `pipe_runtime.py` ke container L.
- **Bentuk:** +2–4 baris per driver (tulis `pipe_runtime.py` bila ada di input repro
  dir, fallback `Path(__file__).with_name(...)`).
- **Risiko:** nyaris nol (dunia segar sudah melakukan hal yang sama). Kompleksitas: kecil.

### R2. Split verdict bucket REPRODUCE — label identifikasi-gejala (spec Mirza)

- **Menyerang:** observability yang sudah 3× menyesatkan autopsi (KH-11/12/15);
  taksonomi §6.4: 27 run `syntax-fail` = 100% artifacts-missing, 0 SyntaxError asli.
- **Kode:** `run_repro_gates.py:65-68` → `repro-missing`;
  `reproduce_gates.py:129-131` → `vacuous-repro`; flip gagal `run_repro_gates.py:100-106`
  → pecah `gold-wont-flip` vs `gold-flip-crash` dengan grep `Traceback`/`SyntaxError`
  atas `flip_run.json` (`patched["output"]`); reason menyesatkan "likely
  gold-unsatisfiable predicate" dibuat di `reproduce_gates.py:86-89`. **Whitelist
  verdict WAJIB ikut:** `emit.py:19-24` (kalau tidak, ValueError) + ikon UI
  `ui/server.py:259-262` (fail-soft).
- **Catatan realita (koreksi subagent):** `py_compile` TIDAK ada di harness — bucket
  `syntax-error` sungguhan paling jujur diderivasi dari grep `SyntaxError` di output
  fresh-run `gate_runs.json`, bukan py_compile host (host 3.12 vs container 3.6).
  `has_fences` juga tak tersedia di gate (state driver, tak dipersist) — kalau mau
  bucket per-mode-loop, persist dulu ringkasan driver (`run_reproduce_gemma.py:506-508`).
- **Risiko:** update tests + konsumen label lama (batch runner aman — pakai `pass_l1`,
  `run_rlfv_batch.py:116-130`). Kompleksitas: kecil-sedang.

### R3. Generalisasi `format_reminder` + port ke driver F/L

- **Menyerang:** keluarga KH-12 (R-1/R-2: 5 case × 3 rerun = 15 run terbakar 40 turn).
- **Kode:** `run_reproduce_gemma.py:471-479` — cabang `has_fences=False` dapat pesan
  generik terlemah; deteksi `"<|tool_call"` di `reply` murah dan tersedia di titik itu
  (`gemma_protocol.py:315-317, 320-332`). **Bonus subagent:** driver FIX
  (`run_fix_gemma.py:343-347`) dan LOCALIZE (`run_localize_gemma.py:326-330`) sama
  sekali TIDAK punya format_reminder — mode gagal yang sama di F/L tak tertangani.
- **Kejujuran klaim:** reminder SAJA terbukti tidak cukup (14855/15902: reminder
  menyala, tetap gagal 40 turn ×3) — ini pelengkap murah, penyelamat sebenarnya
  adalah R5 (watcher). Kompleksitas: kecil.

### R4. Fix encoding checker (V-C) — `charmap` Windows atas output non-ASCII

- **Menyerang:** V-C (3 case astropy; pasti kambuh di base non-ASCII lain).
- **Kode:** `eval/swebench_checker.py:141` tulis UTF-8; `grading.py:58` paket swebench
  baca tanpa encoding → cp1252. Dua opsi subagent: (1) **disarankan** — tulis salinan
  log ber-encoding `locale.getpreferredencoding(False), errors="replace"` khusus untuk
  `grade_log` (marker/nama test ASCII, artefak asli tetap UTF-8); (2) batch runner set
  `PYTHONUTF8=1` di env subprocess checker (`run_rlfv_batch.py:300-302`).
- Kompleksitas: kecil.

### R5. Mechanical-trigger injection, habitat INTRA-RUN (watcher) — DESAIN FINAL Mirza 2026-07-21

**Pola umum (berlaku R5 & R9, difinalkan Mirza via diskusi Telegram 2026-07-21):**
*trigger MEKANIS dari sinyal yang harness saksikan sendiri → suntik informasi
GOLD-BLIND yang menyadarkan model arahnya salah.* Layer product penuh: HARAM
menyuntikkan informasi/clue turunan gold ke model dalam bentuk apa pun. (Dev layer
tetap bebas meng-expose gold di log/artefak untuk dikonsumsi bot analis.)

- **Menyerang:** R-1/R-2/R-4/R-6 (fixed-point temp-0; 35+ turn terbuang per run).
- **Trigger intra-run (semua terbukti muncul di korpus; K & threshold = kalibrasi):**
  1. ≥K reply byte-identik (14411/15851: 40 turn).
  2. ≥K turn beruntun dengan 0 aksi ter-parse (`parse_actions` kosong).
  3. Marker `<|tool_call` di reply (protokol native model — pasti salah format).
  4. ≥K eksekusi `python3 repro.py` padahal file tak pernah ter-persist
     ("rerun file-hantu", 14855/15902).
  5. Exception signature identik ≥K di output `[exec]` (App-churn `__init__
     unexpected keyword` s/d 37×/run) → arahkan inspeksi API langsung.
     *Pengecualian:* signature `No module named 'pipe_runtime'` BUKAN trigger —
     itu bug harness, obatnya R1 (LV-09).
  6. Command identik + output identik ≥K (grep sama 40×, 14411).
  7. DONE-rejected ≥K dengan alasan sama (11564: 6× friksi PASS_OBSERVABLE).
  8. Turn ≥X dan `observed_fail` masih False (churn produktif 12125, 66 exec) →
     "you have not yet observed the failure; re-read the issue".
- **Aksi (urutan Mirza):** (1) **putus-dini** pakai `break` BUKAN `emit_abort` (biar
  artefak tersalin di `run_reproduce_gemma.py:489-501` dan gate tetap memvonis —
  hindari konflik dua-penulis-verdict, temuan bonus #6), lalu untuk trigger yang
  masih recoverable: (2) **inject pesan mekanis UNIK** (nomor turn + fakta yang
  disaksikan, mis. parse-failure eksplisit) ke `feedback_parts` — di temp 0.0,
  mengubah konteks adalah satu-satunya jalan keluar dari attractor.
- **Kode:** loop turn `run_reproduce_gemma.py:315-321` — history reply SUDAH ada di
  `messages`. Semua sinyal trigger di atas base-world (disaksikan driver) → gold-blind
  by construction.
- **Risiko:** false-positive reply pendek sah — kalibrasi K & normalisasi. Kompleksitas: kecil-sedang.
- **⚠ R5 TERPASANG HANYA di REPRODUCE (bukan FIX/LOCALIZE)** — konfirmasi kode +
  inventory. **Kandidat PORT ke FIX diperkuat bukti 2026-07-22 (autopsi 15347 r2,
  temuan Mirza):** di fase FIX, model memasang fix BENAR (identik gold) lalu
  menembakkan `python /testbed/.pipe/repro.py` **58× identik dalam SATU reply**
  (semua PASS) sebelum DONE — degenerate repetition, boros budget. Trigger #6
  (command+output identik ≥K) akan menangkapnya. Benign di 15347 (keburu hijau,
  kanari stabil) TAPI pola yg sama di case sulit = bakar budget besar. **Catatan
  desain porting:** trigger #1 (reply byte-identik) TAK cukup untuk FIX (reply FIX
  bervariasi — stokastisitas KH-20, §-A0d); yang efektif di FIX = trigger #5/#6/#7
  (signature/command/output/DONE-reject berulang), bukan byte-identity reply.
  Sekaligus flag mekanis "≥K PASS identik" bisa memicu cek-vacuous otomatis (§3a).

### R6. Dedup papan skor batch saat resume

- **Menyerang:** integritas angka pelaporan (bukan kelas kegagalan model).
- **Kode:** `run_rlfv_batch.py:347-369` meng-append `results` lintas resume → satu case
  bisa terhitung >1 di ringkasan `:375-376`. Dedup per case saat merangkum. Prune
  sendiri SUDAH benar dihitung gagal (fail-safe `should_prune_fix` :86-114).
- Kompleksitas: kecil.

### R7. Port fix CRLF ke driver LOCALIZE (bonus subagent, bug class dikenal)

- **Kode:** `run_localize_gemma.py:90-95` `docker_write_file` masih `text=True` —
  bug CRLF yang sudah diperbaiki di R (`run_reproduce_gemma.py:152-161`, bytes mentah)
  dan F (:129-137) belum diport ke L. Vault: CRLF pernah merusak SEMUA file tulisan
  model secara retroaktif ("kadang yang harus diautopsi bukan model, tapi harness").
- Kompleksitas: kecil.

---

## §2 — TIER 2: mekanis, sedang, dampak besar

### R8. Trace hook via `.pth` site-packages (bukan PYTHONPATH) — tutup L-B untuk selamanya

- **Menyerang:** L-B (14580, satu-satunya L-wall; LOCALIZE mati sebelum LLM).
- **KOREKSI PENTING (subagent kode, membantah taksonomi §L-B):** follow-child trace
  SUDAH diimplementasikan (`localize_trace.py:98-107` + `trace_sitecustomize.py` via
  PYTHONPATH). Akar 14580 yang sebenarnya: **repro-nya sendiri menimpa PYTHONPATH**
  (`env["PYTHONPATH"] = str(testbed)` di repro.py) → child kehilangan hook. Bukan
  "follow-fork belum ada".
- **Bentuk:** pindahkan hook ke site-packages container via file `.pth` satu-baris
  (dieksekusi saat site-init APA PUN isi PYTHONPATH, selama `TRACE_POOL_DIR`
  terwariskan). Alternatif "gate R melarang repro subprocess" TIDAK disarankan —
  repro subprocess (manage.py) pola sah yang difasilitasi App.
- Kompleksitas: kecil-sedang. Taksonomi L-B akan kuperbarui dengan akar terkoreksi ini.

### R9. Mechanical-trigger injection, habitat ANTAR-RERUN — DESAIN FINAL Mirza 2026-07-21

(Pola umum & prinsip = R5. Opsi (b) feedback-injection deterministik; temp tetap 0.0.)

- **Menyerang:** rerun byte-identik = budget 3-rerun membeli 0 informasi (14411 dkk).
- **Kode:** konteks awal `run_reproduce_gemma.py:299-304`; driver tahu `args.rerun` dan
  bisa membaca artefak r(N−1): `verdict.json`, `events.jsonl` (exit `detail.failures`),
  `gate_runs.json`, `files/repro.py`. Append blok ke pesan user pertama.
  Deterministik: artefak beku → konteks beku → reproducible.
- **KEBIJAKAN KONTEN — STRICT (keputusan Mirza 2026-07-21, menggantikan usulan
  "dua-tier" bot-04 yang masih membawa 1 bit turunan gold):**
  - **Kegagalan base-world → boleh VERBATIM:** anti-vacuous PASS-at-base, token/
    format/artefak hilang, idempotency, output repro di base (`gate_runs.json`),
    crash scaffolding sendiri. Semua disaksikan tanpa gold.
  - **Flip-fail → TANPA alasan sama sekali.** Yang boleh disuntikkan hanya: repro
    attempt sebelumnya + output base-world-nya + directive diversity ("this exact
    approach was already attempted; produce a fundamentally different reproduction
    approach"). JANGAN katakan "predicate not satisfied by the fix" atau bentuk
    apa pun yang mengabarkan hasil dunia ber-patch.
  - **HARAM permanen:** isi `flip_run.json` / output & traceback dunia ber-gold-patch /
    apa pun yang menunjuk lokasi, perilaku, atau keberadaan efek gold.
- **Catatan integritas pengukuran:** rerun ber-injeksi ≠ comparable dengan rerun
  historis tanpa injeksi — papan skor wajib menandai rezim (lesson "kontrol budget
  saat klaim lift"). Kejujuran epistemik: keputusan me-rerun pasca flip-fail memang
  terkondisi gold di level ORKESTRASI, tapi model ber-konteks-segar tidak melihat
  fakta itu; yang dijaga strict adalah KONTEN yang masuk konteks model.
- Kompleksitas: kecil-sedang.

### R10. Gate L membaca `trace_pool.json` (lapisan kedua untuk run tembus-tanpa-DONE)

- **Menyerang:** lubang nyata temuan subagent: run L yang HABIS max-turns tanpa DONE
  tetap menulis `files/localize.md` (`run_localize_gemma.py:334-337`) TANPA pernah
  melewati cek pool (cek kandidat-⊆-pool hari ini hanya di jalur DONE driver,
  :236-258) — artefak itu bisa qualified di gate. Sinyal blind (bukan gold) — sejalan
  keputusan Mirza (2) untuk Kelas-A, dan pool SUDAH dipersist (`files/trace_pool.json`,
  :206-208).
- **Kode:** `run_localize_gates.py:56-76` (gate tak membaca pool sama sekali hari ini).
  Rekomendasi: fail-open untuk run legacy tanpa trace_pool.json.
- **Kejujuran cakupan:** ini menaikkan integritas gate, TAPI tidak menyerang akar
  Kelas-A yang dominan (recall-miss/gold-unguessable — model menunjuk file salah yang
  MEMANG ada di pool). Lever recall Kelas-A sesungguhnya masih terbuka (lihat §4).
- Kompleksitas: kecil.

### R11. Graceful-shutdown: verdict `interrupted` (V-E/R-7)

- **Menyerang:** 9 run bangkai tanpa verdict.json; false-live dashboard (sisi-tulis;
  komplementer fix mtime `9476fc6`).
- **Kode:** verdict normal ditulis GATE (`emit.py:101-117`); driver hanya saat crash
  via `emit_abort` — **KeyboardInterrupt/SystemExit lolos tanpa verdict** (except
  Exception, bukan BaseException — `run_reproduce_gemma.py:314-487`). Bentuk: signal
  handler + `except BaseException`/`finally` → `emit_abort(em, "interrupted")`;
  kalau mau label verdict literal, tambah ke `VERDICTS` `emit.py:19-24`.
- **Risiko jujur (subagent):** di Windows `taskkill /F` tak memberi kesempatan handler;
  efektif hanya untuk Ctrl+C/SystemExit — nilai nyata ada tapi jangan overclaim. Plus
  kesadaran dua-penulis-verdict (gate menimpa abort bila batch tetap lanjut :222-228).
- Kompleksitas: sedang (3 driver × titik).

### R12. Guard timeout `docker_exec` di FIX + retry backoff `chat()` (bonus subagent)

- `run_fix_gemma.py:120-126` tanpa penanganan `TimeoutExpired`+restart yang sudah ada
  di R (:136-149) → satu command hang mengabort SELURUH run FIX, bukan attempt itu.
  `chat()` timeout 600s retry sekali tanpa backoff (R :318-320, F :247-249, L :262-264)
  — dua kegagalan endpoint beruntun = crash run (relevan untuk tes max-2 concurrent).
- Kompleksitas: kecil (port pola R) + kecil.

---

## §3 — TIER 3: butuh desain / keputusan, dampak tinggi jangka menengah

### R13. LV-06 `run_once()` — mode one-shot pipe_runtime.App

- **Menyerang:** kelas bernama terbesar korpus (`unexpected keyword` 33 kejadian/8 case;
  App one-shot 27 kejadian/5 case; +5× "failed to become ready" 14752).
- **Kode:** `pipe_runtime.py:29,43-45` — `ready_token` WAJIB, tak ada jalur one-shot.
  Bentuk: fungsi modul `run_once(cmd, cwd, timeout)` ±40-60 baris py3.6-safe, return
  `(exit_code, lines)` + helper `contains()`; WAJIB didokumentasikan 3-4 baris di
  `reproduce_prompt.md` rule `app-runtime` — lever mati kalau model tak tahu API-nya.
  (Ini contoh prompt-change yang SAH: mengubah cara menurunkan literal/API, bukan
  menuntut mekanisme asing.)
- **Risiko:** model memakai run_once saat butuh App penuh — mitigasi kalimat kontrak.
- Kompleksitas: sedang (kode kecil, permukaan kontrak + tests).

### R14. Kontrol positif K4 semi-mekanis — slot `CONTROL-MARKER` opt-in

- **Menyerang:** K4 = sumbu dominan lintas-batch (45/52 case, 87%); bukti kausal
  load-bearing 11999 (absen K4 → false-flip yang ditangkap P2P).
- **Bentuk (subagent, jujur):** slot repro.md baru opt-in `CONTROL-MARKER: <literal>`;
  gate cek literal tercetak di output fresh-run SEBELUM `REPRO_STATUS` (data sudah di
  `gate_runs.json`) + verifikasi anti-karang gaya `literal_emitted_by_script`
  (`gemma_protocol.py:139-150`).
- **Plafon jujur:** K4 penuh TIDAK bisa mekanis tanpa gold — mesin tak bisa memutuskan
  (1) apakah case butuh kontrol, (2) apakah kontrolnya bermakna. Yang realistis:
  "kalau model MENGKLAIM kontrol, klaimnya diverifikasi tercetak". Empat case korpus
  menulis kontrol positif tanpa diminta — bentuknya murah dan sudah terbukti ada.
- Kompleksitas: sedang; nilai naik bila dipasangkan penguatan kontrak (opt-in didorong).

### R15. LV-14 detektor dua-arah region-hunk (realm EVAL — gold-aware yang SAH)

- **Menyerang:** F-2/F-3 + seluruh H-3 (12 case hijau-longgar): `line_overlap`
  menyesatkan dua arah (11999 superset overlap=true; 12907 rewrite overlap=false).
- **Bentuk:** di `eval/fix_gold_eval` — hitung jumlah region hunk gold vs patch per
  file; mismatch (patch<gold = subset; patch>gold = superset) + `line_overlap=true`
  → flag. Murah, mekanis, hidup di `eval/` (boleh lihat gold — bukan product harness).
- Kompleksitas: kecil-sedang. Nilai: papan skor & autopsi, bukan loop model.

### R16. Tutup celah pagar edit FIX (harta vault — bug TERBUKA yang belum di katalog)

- **Dari F-dev Log vault (Akar #2):** pre-check `off-candidate-files` menghitung
  tracked-modified saja; ekstraksi `fix.diff` pakai `git add -N` (untracked ikut) —
  **patch off-candidate non-kosong bisa lolos pagar**. Juga cocok dengan gejala
  taksonomi "file kosong/stray bocor ke diff" (12497, 13447, 11999 +2 stray).
- **Bentuk:** samakan himpunan file kedua titik (semangat LV-03). Butuh keputusan
  desain kecil: himpunan mana yang jadi acuan.
- Kompleksitas: kecil-sedang.

### R17. LV-05/judge → arah LV-13(a): kewajiban bukti > filter kategori

- **Menyerang:** R-3 (2 wall + ongkos turn besar di ≥5 case; bukti terbaru 11564 r3 &
  14752: LV-05(b) mekanika-saja TIDAK menyelamatkan — keberatan judge kategori
  `correctness`/action-path).
- **Bentuk minimum yang didukung bukti:** judge TIDAK boleh membatalkan checkpoint
  yang observed-FAIL-at-base (bukti yang sudah disaksikan driver); keberatannya
  didemosikan jadi advisory bila checkpoint plausibel-flip. Sejalan LV-08
  (reinstatement checkpoint).
- **Kehati-hatian:** judge juga penangkal repro-halusinasi; perubahan ini butuh desain
  + uji pada case yang dulu justru diselamatkan judge. Filter frontier-baseline layak
  dipakai dulu di 14752/11564. Kompleksitas: sedang-besar.

### R20. Parse format `<|tool_call>` native model = aksi valid (UNLOCK token-loop) — BARU 2026-07-22

- **Menyerang:** **dinding UNLOCK R-1/R-2 token-loop** (keluarga KH-12: 15851, 14411,
  13265, 14855, 15902) — yang R3/R5 TIDAK tutup (mereka cuma efisiensi+observability).
- **Bukti pemicu (batch-2, 15851 r4-r6, 2026-07-22):** dgn R2+R3+R5 aktif — label kini
  jujur (`repro-missing`), turn anjlok 40→4-12 (R5 memutus loop), TAPI **tetap
  repro-missing**: model ngotot emit `<|tool_call>` native, `parse_actions` cuma paham
  fenced-block → 0 aksi → repro.py tak pernah ketulis. Akar = instruction-following
  (model pakai "dialek" tool-call sendiri); R3/R5 tak memaksanya berubah.
- **Bentuk (dua arah, perlu desain):** (a) **adaptasi ke model** — perluas
  `parse_actions` mengenali `<|tool_call>…<tool_call|>` native model & petakan ke
  action-type yang sama (bash/file/…); (b) **paksa model** — penegakan format lebih
  keras (R3-style, sudah terbukti lemah). (a) lebih menjanjikan (terima dialek model).
- **Kaitan riset bot-05 (sub-problem 4 tool-call robustness):** **mini-SWE-agent**
  ("no tool-calling API, bash saja") = preseden yang menghindari masalah ini sepenuhnya
  — **riset-lanjutan mini-SWE-agent WAJIB dulu** untuk menginformasikan desain (a) vs
  pendekatan bash-only. Lihat [[adopsi-eksternal-dari-riset]].
- **Risiko:** format native mungkin tak memetakan bersih ke grammar aksi kita (ambiguitas
  parse); butuh contoh riil `<|tool_call>` model + TDD. **Status: KANDIDAT, research-gated**
  (butuh riset mini-SWE-agent + desain). Kompleksitas: sedang-besar.

---

## §4 — JANGAN di-invest (bukti negatif eksplisit)

1. **Git-history sebagai sinyal LOCALIZE** — P25: load-bearing 0 dari 6 case.
2. **Gate R melarang repro subprocess** — pola sah (manage.py); fix yang benar = R8.
3. **K4 full-mekanis** — tak terdecidable tanpa gold (lihat plafon R14).
4. **"Daya beda F2P rendah" sebagai lever** — batas metodologi (n=2); yang layak
   hanya harness pengukur sabotase, itu pun sebagai alat riset.
5. **Seeded-temperature antar-rerun** — DITOLAK Mirza (flakiness vonis); opsi (b) R9.
6. **Rule prompt yang menuntut mekanisme asing** — pola gagal terdokumentasi (R-a 0/3,
   R-b 1/3); prompt hanya untuk menurunkan literal/API (Paket Predikat 6/6, R13).
7. **Lever recall Kelas-A via cek-gold di gate produk** — melanggar gold-blind
   (keputusan tegas Mirza). Catatan terbuka: akar dominan Kelas-A (gold-unguessable)
   belum punya lever blind yang menyerang akarnya; kandidat riset: L-b "layer-diverse
   shortlist" dari vault (kandidat wajib ≥2 lapisan arsitektur — belum dipasang).

---

## §5 — Koreksi terhadap dokumen sebelumnya (dari verifikasi kode)

1. **Taksonomi §L-B:** "trace-injection tidak mengikuti fork" → TIDAK AKURAT.
   Follow-child sudah ada (sitecustomize via PYTHONPATH); akar 14580 = repro menimpa
   PYTHONPATH di env child. Akan kuperbarui di taksonomi (derajat: DIPERSEMPIT).
2. **Spec split-verdict:** bucket `syntax-error` tidak bisa dari `py_compile` (tak ada
   di harness; beda versi Python host/container) — derivasi dari output run.
   `has_fences` tak tersedia di gate tanpa persist ringkasan driver.

## §6 — Urutan pemasangan yang kusarankan (kalau Mirza setuju mulai)

**Gelombang 1 (sehari, risiko rendah):** R1 (LV-09+kembar) → R2 (split verdict) →
R3 (format_reminder×3 driver) → R7 (CRLF L) → R4 (encoding checker) → R6 (dedup papan).
**Gelombang 2:** R5 (watcher) + R9 (feedback-injection; butuh keputusan garis
gold-blind) + R8 (.pth trace) + R10 (gate-L pool) + R12 (timeout FIX).
**Gelombang 3 (desain dulu):** R13 (run_once+kontrak) → R14 (CONTROL-MARKER) →
R15 (detektor dua-arah) → R16 (pagar edit FIX) → R17 (judge).

**Protokol validasi tiap lever (dari lesson vault):** uji pada case kelas-target DAN
sampel kelas lain (lever bisa merusak yang mudah); wasit = checker L2 bukan repro-flip;
budget dikontrol saat klaim lift; 41-case belum-tersentuh + grup-3/4 = holdout alami;
status semua lever try-then-drop.

---

## Addendum 2026-07-22 — integrasi temuan grup-3/4 bot-03 (KH-16/17/18)

Dua kandidat lever bot-03 yang layak MASUK Gelombang 1 (Tier-1; detail di ekor
[[katalog-lever]]):

- **R18 = KL-G3-1 — `git apply --check gold.patch` saat setup case, gagal-KERAS.**
  Menyerang kelas baru R-8 (5/97 gold korup → flip vacuous, mislabel `wrong-logic`,
  salah-atribusi akar-MODEL). Akar prepare_cases `patch.rstrip()` sudah di-fix
  (`471cb6d`); lever ini mencegah kambuh dari jalur setup mana pun. Kompleksitas: kecil.
- **R19 = KL-G3-2 — `should_prune_fix` keying `qualified is False`, BUKAN
  `file_match is False`** (`run_rlfv_batch.py:113`). Menyelaraskan prune dgn semantik
  shortlist (FIX mengiterasi seluruh kandidat). **Bukti solve-recovery konkret:**
  13033 di-prune salah → re-run tanpa prune → resolved=true di file gold, 0 regresi.
  Kompleksitas: kecil.

Koreksi/caveat atas rekomendasi yang sudah ada:

- **R15 (detektor hunk dua-arah) dapat blind-spot terukur:** 12284 = over-broad DI
  DALAM satu hunk region-gold (jumlah region gold==model) — mismatch-region tak
  menangkapnya. R15 tetap layak (menangkap subset 14365 & superset 11999), tapi jangan
  diklaim menutup seluruh F-2/F-3; divergensi intra-hunk tetap butuh §3b bacaan diff.
- **Aturan §3a untuk semua tooling papan skor:** deteksi lulus-palsu pakai **FIX
  `gold_eval.file_match`** (patch akhir), BUKAN l-dev/localize file_match (over-flag —
  kasus 11964). Relevan untuk siapa pun yang menulis detektor/dashboard.
- **R6 (dedup papan batch) makin relevan:** re-run pasca-repair gold + re-run
  tanpa-prune menambah entri ganda per case di state batch.

---

*TDD wajib untuk semua perubahan harness (`python -m pytest` hijau sebelum commit);
tests yang tersentuh minimal: test_reproduce_gates, test_pipe_runtime*, test_ui_*.
Trailer `Agent: <bot>`.*

## §7 — RE-PRIORITISASI G2 (keputusan Mirza 2026-07-22 malam, pasca rate-gating §-A0f)

Empat lever baru sesi retest-rate (bukti: [[katalog-lever]] entri claude-mac 22-07,
KH-21, papan `artifacts/papan-skor-rate-origin-r1-mac-g1.md`) menggeser lineup lama
(R5+R9+R8+R10+R12). **G2-BARU, urutan pemasangan:**

1. **N1 — watcher reply-hash di loop FIX** (habitat-FIX dari R5; trigger byte-identity
   direhabilitasi KH-21). 2 spesimen same-day (12184 r12: 32×; 15388 r9: 30×+6×),
   hematan ~30 turn/kejadian. Mekanis: md5(reply_N)==md5(reply_N−1) 2× berturut →
   akhiri attempt dini (memicu rotasi kandidat yang SUDAH terbukti menyelamatkan r9
   12184). Kecil, deterministik, gold-blind.
2. **N4 — relaksasi attempt-lock berbasis-shortlist**: bila model berulang (≥3×
   `off-candidate-files`) menyentuh file yang ADA di candidates.md (peringkat lebih
   rendah), pindahkan lock ke kandidat itu alih-alih terus menolak. Bukti 12184: KEDUA
   draw "tahu" resolvers.py di tengah attempt-1 tapi dipenjara. Gold-blind (hanya
   perilaku model + shortlist produk).
3. **R12 (peta lama, prioritas NAIK) — timeout+retry backoff `chat()` & guard
   `docker_exec` FIX.** Bukti baru: 2 run mati-gantung tanpa timeout (12184 r11,
   15388 r9 — koneksi half-open pasca sleep host). Menyerang kelas infra-hang yang
   baru saja memakan 2 slot.
4. **N2 — audit konsistensi evidence↔file di shortlist LOCALIZE**: cek mekanis simbol
   yang dikutip evidence benar-benar ada di file yang diklaim (grep, gold-blind);
   demosi/koreksi kandidat yang gagal. Menyerang akar hulu dua varian (12184: file
   salah; 15388: teori salah di file benar).

**Ditunda dari lineup lama:** R9 (injeksi antar-rerun; desain final tetap berlaku,
tak ada bukti baru sesi ini), R8/.pth + R10 (kelas L-B tak muncul di rate-gating) →
kandidat G3. **N3 (perkuat oracle repro)** dilebur ke R14 (CONTROL-MARKER, G3) —
butuh desain, jangan dikodekan tergesa.

Protokol validasi tetap §6: uji kelas-target + kanari (stabil 11049/15347/6938 n=3
same-session; goyang rate-based), wasit L2, rezim berlabel, try-then-drop.
Orkestrasi: `--parallel ≤7` (izin Mirza, endpoint eksklusif).
