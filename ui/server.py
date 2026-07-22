"""UI log viewer sederhana untuk artifacts harness SWE-bench.

Stdlib only (Python 3.12). Baca-saja: tidak pernah menulis ke artifacts.
Kontrak data: docs/kontrak-output.md (schema_version 1.0.0).

Jalankan:
    python ui\\server.py [--root <artifacts_dir>] [--port 8766]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_PORT = 8766
DEFAULT_TAIL = 200
_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

# Ambang keaktifan run tanpa verdict.json (detik). Run tanpa verdict yang
# file aktivitasnya (console.log/events.jsonl) di-update <= ambang ini
# dianggap "(live)"; lebih lama -> "(stale?)" (dibunuh/ditinggalkan).
# Sengaja longgar (5 menit): sebuah REPRODUCE aktif meng-update console.log
# tiap turn dan jeda antar-turn jarang > beberapa menit — jangan salah cap
# run lambat-tapi-hidup sebagai stale.
STALE_THRESHOLD_SECONDS = 300


# --- logika inti (dites di tests/test_ui_core.py) ---------------------------

def validate_name(s: str) -> bool:
    """Nama campaign/run_id yang aman dipakai sebagai komponen path."""
    return bool(s) and bool(_NAME_RE.match(s)) and ".." not in s


def tail_lines(path: Path, n: int) -> list[str]:
    """N baris terakhir sebuah file teks; file hilang/rusak -> []."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return text.splitlines()[-n:] if n > 0 else []


def list_campaigns(root: Path) -> list[str]:
    """Nama subdirektori artifacts (satu per kampanye), terurut."""
    try:
        return sorted(p.name for p in Path(root).iterdir() if p.is_dir())
    except OSError:
        return []


def list_runs(campaign_dir: Path) -> list[dict]:
    """Daftar run sebuah kampanye: [{run_id, verdict, wall}].

    Sumber utama runs.jsonl (baris rusak dilewati); run yang hanya ada
    sebagai direktori tetap ikut (fallback listing dir).
    """
    campaign_dir = Path(campaign_dir)
    runs: dict[str, dict] = {}

    for line in tail_lines(campaign_dir / "runs.jsonl", 10_000):
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        run_id = obj.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            continue
        entry = runs.setdefault(run_id, {"run_id": run_id,
                                         "verdict": None, "wall": None})
        if obj.get("event") == "end":
            entry["verdict"] = obj.get("verdict")
            entry["wall"] = obj.get("wall")

    try:
        for p in sorted(campaign_dir.iterdir()):
            if p.is_dir():
                runs.setdefault(p.name, {"run_id": p.name,
                                         "verdict": None, "wall": None})
    except OSError:
        pass

    return list(runs.values())


def run_turns(run_dir: Path) -> int | None:
    """Jumlah turn model: [gemma tN] terbesar di console.log."""
    lines = tail_lines(Path(run_dir) / "console.log", 100_000)
    best = None
    for line in lines:
        m = re.match(r"\[gemma t(\d+)\]", line)
        if m:
            n = int(m.group(1))
            best = n if best is None else max(best, n)
    return best


_CAMPAIGN_LABELS = {"r-dev": "REPRODUCE", "l-dev": "LOCALIZE",
                    "f-dev": "FIX and VERIFY"}

# Stage pipeline yang tabnya selalu tampil di dashboard, dalam urutan
# pipeline REPRODUCE -> LOCALIZE -> FIX (permintaan Mirza 2026-07-20:
# tab FIX tampil walau kampanye f-dev belum punya run — kosong dulu).
# TANPA tab keempat untuk VERIFY (keputusan Mirza 2026-07-20): checker L2
# adalah pekerjaan VERIFY di dalam tab "FIX and VERIFY" itu sendiri.
_PIPELINE_STAGES = ("r-dev", "l-dev", "f-dev")


def campaign_label(name: str) -> str:
    """Label tab manusiawi (masukan Mirza); kampanye tak dikenal tampil
    apa adanya."""
    return _CAMPAIGN_LABELS.get(name, name)


def campaign_phase(campaign: str) -> str:
    """Kode fase utk tombol 'copy to clipboard' di tabel utama (permintaan
    Mirza 2026-07-21): r-dev (REPRODUCE) -> "R", l-dev (LOCALIZE) -> "L",
    f-dev (FIX/VERIFY) -> "FV". Prefix-based supaya konsisten dgn konvensi
    kampanye lain di file ini (startswith 'l-'/'f-'). Tak dikenal -> ""."""
    if campaign.startswith("r-"):
        return "R"
    if campaign.startswith("l-"):
        return "L"
    if campaign.startswith("f-"):
        return "FV"
    return ""


def copy_case_json(case_id: str, campaign: str, rerun: str = "") -> str:
    """String JSON yang disalin tombol clipboard, format PERSIS
    {"case": "<id>", "phase": "<R|L|FV>", "run": "<rN>"} (spasi setelah titik
    dua/koma, double-quote, urutan case->phase->run) — dibangun server-side
    lalu ditempel ke atribut data. rerun = bagian rN run_id baris (mis. "r1");
    format run_id tak dikenal -> "run": "" (fail-soft)."""
    return json.dumps({"case": case_id, "phase": campaign_phase(campaign),
                       "run": rerun or ""})


def with_stage_tabs(campaigns: list[str]) -> list[str]:
    """Tambahkan stage pipeline yang belum punya direktori artifacts —
    tabnya tetap tampil (kosong) supaya pipeline terlihat utuh."""
    return list(campaigns) + [s for s in _PIPELINE_STAGES
                              if s not in campaigns]


def order_campaigns(campaigns: list[str]) -> list[str]:
    """Urutan tab = urutan pipeline (r-dev REPRODUCE selalu pertama,
    permintaan Mirza); kampanye di luar pipeline menyusul terurut nama."""
    return ([s for s in _PIPELINE_STAGES if s in campaigns]
            + [c for c in campaigns if c not in _PIPELINE_STAGES])


def run_sort_key(run_id: str) -> tuple:
    """Kunci sort run: nomor rerun rN (numerik), fallback string."""
    m = re.search(r"--r(\d+)$", run_id)
    return (int(m.group(1)) if m else -1, run_id)


def split_run_id(run_id: str) -> tuple[str, str]:
    """Pecah run_id <campaign>--<case_id>--r<N> jadi (case_id, "rN")
    (permintaan Mirza 2026-07-19: kolom case & run terpisah di dashboard).
    Format tak dikenal -> (run_id, "") supaya tetap tampil apa adanya."""
    m = re.match(r"^.+?--(.+)--(r\d+)$", run_id)
    return (m.group(1), m.group(2)) if m else (run_id, "")


def run_started_ts(run_dir: Path):
    """Datetime (aware) event pertama run; None bila tak terbaca."""
    from datetime import datetime
    try:
        first = (Path(run_dir) / "events.jsonl").read_text(
            encoding="utf-8", errors="replace").splitlines()[0]
        return datetime.fromisoformat(json.loads(first)["ts"]).astimezone()
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None


def run_started_str(run_dir: Path) -> str:
    """Tanggal-jam mulai run, format ringkas "YYYY-MM-DD HH:mm" tanpa offset
    (permintaan Mirza 2026-07-20: tanggal pengujian tampil di dashboard).

    Sumber utama: field `started` verdict.json (ISO +07:00). Run hidup /
    legacy tanpa verdict -> fallback ts event pertama events.jsonl.
    Tak ada / cacat -> "?" (fail-soft, jangan crash)."""
    from datetime import datetime
    run_dir = Path(run_dir)
    raw = None
    try:
        vj = json.loads((run_dir / "verdict.json").read_text(encoding="utf-8"))
        raw = vj.get("started") if isinstance(vj, dict) else None
    except (OSError, ValueError):
        raw = None
    if raw is None:
        try:
            first = (run_dir / "events.jsonl").read_text(
                encoding="utf-8", errors="replace").splitlines()[0]
            ev = json.loads(first)
            raw = ev.get("ts") if isinstance(ev, dict) else None
        except (OSError, ValueError, IndexError):
            raw = None
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return "?"


def sort_runs_desc(runs: list[dict], campaign_dir: Path) -> list[dict]:
    """Urut desc berdasar started datetime (event pertama) — permintaan
    Mirza 2026-07-19: run terbaru case mana pun tampil di halaman pertama
    (nomor rerun per-case, jadi r1 case baru > r44 case lama). Fallback
    run tanpa events.jsonl: nomor rerun."""
    from datetime import datetime, timezone
    epoch = datetime.min.replace(tzinfo=timezone.utc)

    def key(r: dict) -> tuple:
        ts = run_started_ts(Path(campaign_dir) / r["run_id"])
        return (ts or epoch, run_sort_key(r["run_id"]))

    return sorted(runs, key=key, reverse=True)


def filter_runs_by_case(runs: list[dict], q: str | None) -> list[dict]:
    """Nyaring run berdasar substring nama case (case-insensitive) — dipakai
    kotak search dashboard (permintaan Mirza 2026-07-21). q kosong/None ->
    daftar apa adanya (tanpa regresi). Match di case_id hasil split_run_id
    supaya "15902"/"django-114" nyaring lintas SEMUA halaman sebelum paginasi."""
    if not q:
        return runs
    needle = q.strip().lower()
    if not needle:
        return runs
    out = []
    for r in runs:
        rid = r.get("run_id")
        if not isinstance(rid, str) or not rid:
            continue
        if needle in split_run_id(rid)[0].lower():
            out.append(r)
    return out


def paginate(items: list, page: int, per_page: int = 15) -> tuple[list, int]:
    """(potongan halaman, total_halaman); page 1-based, di-clamp."""
    total = max(1, -(-len(items) // per_page))
    page = max(1, min(page, total))
    start = (page - 1) * per_page
    return items[start:start + per_page], total


def verdict_icon(v) -> str:
    """✅ utk pass/flip, ❌ utk kelas gagal; abort/None polos
    (permintaan Mirza 2026-07-19)."""
    if v in ("pass", "flip"):
        return "✅ "
    if v in ("fail", "syntax-fail", "wrong-logic", "timeout",
             "no-flip", "empty-patch",
             # R2 split-verdict: symptom-identifying REPRODUCE labels
             "repro-missing", "vacuous-repro", "syntax-error",
             "gold-wont-flip", "gold-flip-crash"):
        return "❌ "
    return ""


def merge_gold_verdict(vtext: str, icon: str, campaign: str,
                       run_dir: Path) -> tuple[str, str]:
    """Merge vonis product L1 dengan lapisan test-system gold_eval.json
    (keputusan Mirza 2026-07-19) — HANYA di render, viewer tetap read-only.

    - vtext bukan "pass" → apa adanya (fail/wrong-logic/abort dst).
    - "pass" + gold_eval.json: qualified=true → pass ✅;
      qualified=false → "wrong-file" ❌.
    - "pass" tanpa gold_eval.json (atau rusak): kampanye "l-*" (konvensi
      LOCALIZE) → "pass (no-eval)" ⏳ supaya beda dari pass penuh;
      kampanye lain (mis. r-dev REPRODUCE) → perilaku lama.
    """
    if vtext != "pass":
        return vtext, icon
    gpath = Path(run_dir) / "gold_eval.json"
    if gpath.is_file():
        try:
            obj = json.loads(gpath.read_text(encoding="utf-8"))
            qualified = obj.get("qualified") if isinstance(obj, dict) else None
        except (OSError, ValueError):
            qualified = None
        if qualified is True:
            return "pass", verdict_icon("pass")
        if qualified is False:
            return "wrong-file", verdict_icon("fail")
        # gold_eval rusak/tanpa field: jatuh ke aturan "belum ada eval"
    if campaign.startswith("l-"):
        return "pass (no-eval)", "⏳ "
    return vtext, icon


# --- panel ringkasan per tahapan (permintaan Mirza 2026-07-20) --------------
# Definisi status per case per stage = "PERNAH QUALIFIED" (keputusan Mirza
# 2026-07-20): case PASS bila ADA >=1 run-nya yang qualified di kampanye tsb.
# Qualified per run:
#   r-dev = verdict pass + pass_l1 true (flip terkonfirmasi).
#   l-*   = L1 pass DAN gold_eval qualified true — konsisten dengan
#           status gabungan merge_gold_verdict di tabel.
# Case FAIL hanya bila TAK PERNAH ada run qualified; kategori+alasan diambil
# dari run TERBARU case itu. verdict.json tak ada/rusak -> "?" (fail-soft).

def latest_runs_by_case(runs: list[dict]) -> dict[str, str]:
    """Map case_id -> run_id run TERBARU (nomor rerun terbesar)."""
    best: dict[str, str] = {}
    for r in runs:
        rid = r.get("run_id")
        if not isinstance(rid, str) or not rid:
            continue
        case, _ = split_run_id(rid)
        if case not in best or run_sort_key(rid) > run_sort_key(best[case]):
            best[case] = rid
    return best


def events_fail_detail(run_dir: Path) -> tuple[list[str], str | None]:
    """(failures exit terakhir, reason abort terakhir) dari events.jsonl.

    Sumber jujur satu-satunya utk alasan detail: event exit membawa
    detail.failures (list) — bila kosong tapi ada detail.flip dgn
    flip_ok=false, kutip flip.reason. Event abort membawa detail.reason
    (crash driver) atau detail.why. Tak terekam -> ([], None).
    """
    exit_fails: list[str] = []
    abort_reason: str | None = None
    for line in tail_lines(Path(run_dir) / "events.jsonl", 10_000):
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        detail = ev.get("detail")
        if not isinstance(detail, dict):
            continue
        if ev.get("event") == "exit":
            fails = detail.get("failures")
            exit_fails = ([str(f) for f in fails]
                          if isinstance(fails, list) else [])
            flip = detail.get("flip")
            if (not exit_fails and isinstance(flip, dict)
                    and flip.get("flip_ok") is False and flip.get("reason")):
                exit_fails = ["flip: " + str(flip["reason"])]
        elif ev.get("event") == "abort":
            abort_reason = detail.get("reason") or detail.get("why")
            abort_reason = str(abort_reason) if abort_reason else None
    return exit_fails, abort_reason


def _wrong_file_reasons(run_dir: Path) -> list[str]:
    """Alasan 'wrong-file' dari gold_eval.json: kandidat vs gold_files."""
    try:
        g = json.loads((Path(run_dir) / "gold_eval.json")
                       .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(g, dict):
        return []
    cand = g.get("candidate_files")
    if not isinstance(cand, list) or not cand:
        # criterion chosen-file-v1: tanpa shortlist, pakai pointed_file
        cand = [g["pointed_file"]] if g.get("pointed_file") else []
    gold = g.get("gold_files") if isinstance(g.get("gold_files"), list) else []
    return ["shortlist: file gold tidak masuk kandidat — kandidat: "
            + (", ".join(str(c) for c in cand) or "?")
            + " vs gold: " + (", ".join(str(f) for f in gold) or "?")]


def read_swebench_eval(run_dir: Path) -> dict | None:
    """swebench_eval.json (checker L2 realm dev) — None bila absen/rusak."""
    p = Path(run_dir) / "swebench_eval.json"
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _fix_verify_status(vtext: str, vj: dict, run_dir: Path) -> dict | None:
    """Status 2-lapisan kampanye f-* (spec checker L2 §6). None -> alur lama.

    PASS = pass_l1 (product, flip) AND resolved (SWE-bench checker).
    Product-pass tanpa eval = WAIT (bukan FAIL palsu). Product FAIL tapi
    resolved=true = ANOMALY (kontradiksi sinyal, flag menonjol)."""
    sw = read_swebench_eval(run_dir)
    resolved = sw.get("resolved") if sw else None
    fix_verdict = ((vj.get("phases") or {}).get("fix") or {}).get("verdict")
    product_pass = fix_verdict == "flip" and vj.get("pass_l1") is True
    if product_pass and resolved is True:
        return {"status": "PASS", "category": "pass (L1+L2)", "reasons": []}
    if product_pass and resolved is False:
        reasons = []
        if sw.get("f2p_failed"):
            reasons.append("F2P gagal: " + ", ".join(
                str(t) for t in sw["f2p_failed"][:5]))
        if sw.get("p2p_failed"):
            reasons.append("regresi P2P: " + ", ".join(
                str(t) for t in sw["p2p_failed"][:5]))
        if not sw.get("patch_successfully_applied", True):
            reasons.append("patch/test_patch gagal apply di dunia VERIFY")
        return {"status": "FAIL", "category": "verify-fail",
                "reasons": reasons or ["resolved=false tanpa detail"]}
    if product_pass:
        return {"status": "WAIT", "category": "product-pass, menunggu VERIFY",
                "reasons": ["swebench_eval.json belum ada — jalankan "
                            "python -m eval.swebench_checker"]}
    if resolved is True:
        return {"status": "ANOMALY",
                "category": "anomaly: product FAIL tapi SWE-bench resolved",
                "reasons": [f"verdict product: {vtext} — kontradiksi sinyal, "
                            "autopsi manual"]}
    return None  # product fail biasa -> alur lama (exit_fails dst.)


def case_status(campaign: str, run_dir: Path) -> dict:
    """Status qualified SATU run sebuah case (lihat definisi di atas).

    Return {"status": "PASS"|"FAIL"|"WAIT"|"ANOMALY"|"?", "category": str,
    "reasons": [str]}. Kampanye "f-*" pakai status 2-lapisan (spec §6):
    PASS = pass_l1 (flip) DAN swebench_eval.resolved; product-pass tanpa
    swebench_eval.json -> WAIT (bukan FAIL palsu); product FAIL tapi
    resolved=true -> ANOMALY (kontradiksi sinyal).
    JUJUR: alasan hanya dari artefak terekam; tanpa detail -> kategori saja.
    """
    run_dir = Path(run_dir)
    vpath = run_dir / "verdict.json"
    if not vpath.is_file():
        return {"status": "?", "category": "tanpa verdict.json", "reasons": []}
    try:
        vj = json.loads(vpath.read_text(encoding="utf-8"))
        phases = {k: (p or {}).get("verdict")
                  for k, p in (vj.get("phases") or {}).items()}
    except (OSError, ValueError, AttributeError):
        return {"status": "?", "category": "verdict.json rusak", "reasons": []}

    vtext, icon = index_row_verdict(phases, vj.get("wall"))
    vtext, icon = merge_gold_verdict(vtext, icon, campaign, run_dir)

    if campaign.startswith("f-"):
        two = _fix_verify_status(vtext, vj, run_dir)
        if two is not None:
            return two

    if vtext == "pass":
        # l-*: merge_gold_verdict sudah menjamin qualified=true di sini
        if campaign.startswith("l-") or vj.get("pass_l1") is True:
            return {"status": "PASS", "category": "pass", "reasons": []}
        return {"status": "FAIL", "category": "pass (flip tak terkonfirmasi)",
                "reasons": ["verdict pass tapi pass_l1 != true — "
                            "flip tidak terekam OK"]}

    if vtext == "wrong-file":
        return {"status": "FAIL", "category": "wrong-file",
                "reasons": _wrong_file_reasons(run_dir)}
    if vtext == "pass (no-eval)":
        return {"status": "FAIL", "category": "pass (no-eval)",
                "reasons": ["gold_eval.json tidak ada — "
                            "belum dievaluasi test-system"]}

    # kategori gagal product (wrong-logic/syntax-fail/fail/abort/...):
    # kutip detail exit/abort dari events.jsonl bila terekam
    exit_fails, abort_reason = events_fail_detail(run_dir)
    reasons = list(exit_fails)
    if vtext == "abort" and abort_reason:
        reasons.append("abort: " + abort_reason)
    return {"status": "FAIL", "category": vtext, "reasons": reasons}


def status_icon(status: str) -> str:
    """Ikon utk status case_status 2-lapisan — dipakai baris tabel index
    kampanye f-* (sinkron dgn panel ringkasan, permintaan Mirza 2026-07-20)
    dan dipakai ulang di caption render_stage_summary."""
    return {"PASS": "✅ ", "FAIL": "❌ ", "WAIT": "⏳ ",
            "ANOMALY": "⚠️ "}.get(status, "")


def stage_summary(campaign_dir: Path, campaign: str,
                  runs: list[dict]) -> dict:
    """Ringkasan stage per definisi "pernah qualified": case PASS bila
    >=1 run-nya qualified (case_status PASS); selain itu status (FAIL/?)
    plus kategori+alasan diambil dari run TERBARU case itu."""
    by_case: dict[str, list[str]] = {}
    for r in runs:
        rid = r.get("run_id")
        if isinstance(rid, str) and rid:
            by_case.setdefault(split_run_id(rid)[0], []).append(rid)
    latest = latest_runs_by_case(runs)
    items = []
    for case_id in sorted(by_case):
        # mulai dari run terbaru (sumber kategori+alasan bila tak pernah
        # qualified), lalu scan run lain: satu saja PASS -> case PASS
        chosen = latest[case_id]
        st = case_status(campaign, Path(campaign_dir) / chosen)
        if st["status"] != "PASS":
            for rid in sorted(by_case[case_id], key=run_sort_key):
                if rid == chosen:
                    continue
                ever = case_status(campaign, Path(campaign_dir) / rid)
                if ever["status"] == "PASS":
                    chosen, st = rid, ever
                    break
        _, rerun = split_run_id(chosen)
        items.append({"case": case_id, "run_id": chosen,
                      "rerun": rerun or chosen,
                      "started": run_started_str(
                          Path(campaign_dir) / chosen), **st})
    return {"total": len(items),
            "pass": sum(1 for i in items if i["status"] == "PASS"),
            "fail": sum(1 for i in items if i["status"] == "FAIL"),
            "wait": sum(1 for i in items if i["status"] == "WAIT"),
            "anomaly": sum(1 for i in items if i["status"] == "ANOMALY"),
            "unknown": sum(1 for i in items if i["status"] == "?"),
            "items": items}


def _pct(x: int, n: int) -> str:
    return f"{round(100 * x / n)}%" if n else "0%"


def _stage_legend(s: dict) -> str:
    """Teks legenda status (dipindah dari tampilan langsung ke modal '[info]',
    permintaan Mirza 2026-07-21). Baris WAIT/ANOMALY hanya bila relevan."""
    return ("PASS = pernah qualified (&ge;1 run); "
            "FAIL = tak pernah qualified, alasan dari run terbaru"
            + ("; ⏳ WAIT = product-pass, menunggu VERIFY"
               if s.get("wait") else "")
            + ("; ⚠️ ANOMALY = product FAIL tapi SWE-bench resolved "
               "(kontradiksi sinyal, autopsi manual)"
               if s.get("anomaly") else ""))


def render_stage_summary(s: dict) -> str:
    """Panel infografik: angka+persen berikut label "[info]" (klik -> modal
    legenda) dan bar bertumpuk CSS. Rincian FAIL/ANOMALY per case sekarang
    dibuka lewat modal saat ikon di tabel utama diklik (bukan lagi di panel);
    daftar WAIT (menunggu VERIFY) tetap collapsible. Tanpa case -> "".
    """
    n = s["total"]
    if n == 0:
        return ""
    head = (f"<b>{n} cases</b> &middot; "
            f"PASS {s['pass']} ({_pct(s['pass'], n)}) &middot; "
            f"FAIL {s['fail']} ({_pct(s['fail'], n)})")
    if s.get("wait"):
        head += (f" &middot; {status_icon('WAIT')}WAIT {s['wait']} "
                 f"({_pct(s['wait'], n)})")
    if s.get("anomaly"):
        head += (f" &middot; {status_icon('ANOMALY')}ANOMALY {s['anomaly']} "
                 f"({_pct(s['anomaly'], n)})")
    if s["unknown"]:
        head += f" &middot; ? {s['unknown']} ({_pct(s['unknown'], n)})"
    # label "[info]" di paling akhir head -> buka modal legenda
    head += " <a class='info-link' onclick='showInfo()'>[info]</a>"
    segs = []
    for cnt, cls in ((s["pass"], "sp"), (s["fail"], "sf"),
                     (s.get("wait", 0), "sw"), (s.get("anomaly", 0), "sa"),
                     (s["unknown"], "su")):
        if cnt:
            segs.append(f"<span class='{cls}' "
                        f"style='width:{_pct(cnt, n)}'></span>")
    parts = ["<div class='summary'><p>", head, "</p>",
             # legenda tersembunyi; isinya disalin JS ke modal saat "[info]"
             "<div id='legendBody' style='display:none'>"
             + _stage_legend(s) + "</div>",
             "<div class='sbar'>", "".join(segs), "</div>"]

    waiting = [i for i in s["items"] if i["status"] == "WAIT"]
    if waiting:
        rows = [f"<tr><td>{html.escape(i['case'])}</td>"
                f"<td class='dim'>{html.escape(i['rerun'])}</td>"
                f"<td class='dim'>{html.escape(i.get('started', '?'))}</td>"
                "</tr>" for i in waiting]
        parts.append(f"<details><summary>menunggu VERIFY ({len(waiting)})"
                     "</summary><table><tr><th>case</th><th>run</th>"
                     "<th>mulai</th></tr>" + "".join(rows)
                     + "</table></details>")
    parts.append("</div>")
    return "".join(parts)


def _fail_reason_text(item: dict) -> str:
    """Teks alasan per-case utk modal ikon FAIL/ANOMALY (kategori + hingga 3
    reason dipotong 200 char, sama seperti rincian tabel lama)."""
    reasons = "; ".join(r[:200] for r in item.get("reasons", [])[:3]) \
        or "(detail tidak terekam)"
    return f"kategori: {item.get('category', '?')}\nalasan: {reasons}"


def run_duration_seconds(run_dir: Path) -> float | None:
    """Durasi run: ts event pertama → `finished` verdict.json; run yang
    belum bervonis (masih hidup) → mtime console.log terakhir."""
    from datetime import datetime
    try:
        first = (Path(run_dir) / "events.jsonl").read_text(
            encoding="utf-8", errors="replace").splitlines()[0]
        start = datetime.fromisoformat(json.loads(first)["ts"])
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None
    end = None
    vpath = Path(run_dir) / "verdict.json"
    if vpath.is_file():
        try:
            end = datetime.fromisoformat(
                json.loads(vpath.read_text(encoding="utf-8"))["finished"])
        except (OSError, ValueError, KeyError, TypeError):
            end = None
    if end is None:
        try:
            end = datetime.fromtimestamp(
                (Path(run_dir) / "console.log").stat().st_mtime).astimezone()
        except OSError:
            return None
    try:
        return max(0.0, (end - start).total_seconds())
    except TypeError:
        return None


def run_liveness(run_dir: Path, now=None) -> str:
    """Status keaktifan run TANPA verdict.json: "live" atau "stale".

    Sinyal keaktifan = mtime TERBARU dari console.log / events.jsonl di run
    dir. Bila (now - mtime_terbaru) <= STALE_THRESHOLD_SECONDS -> "live";
    lebih lama -> "stale" (run dibunuh/ditinggalkan dari luar; ia tak akan
    pernah menulis verdict.json sehingga dulu tampil "(live)" selamanya).

    `now` opsional utk testability: epoch float ATAU datetime; default
    time.time(). KEDUA file tak ada -> "stale": tanpa bukti keaktifan sama
    sekali, lebih jujur menandai perlu-diperiksa daripada meng-klaim hidup
    (run yang benar-benar berjalan selalu menulis console.log/events.jsonl).
    """
    import os
    import time
    from datetime import datetime
    if now is None:
        now = time.time()
    elif isinstance(now, datetime):
        now = now.timestamp()
    run_dir = Path(run_dir)
    latest = None
    for name in ("console.log", "events.jsonl"):
        try:
            m = os.path.getmtime(run_dir / name)
        except OSError:
            continue
        latest = m if latest is None else max(latest, m)
    if latest is None:
        return "stale"
    return "live" if (now - latest) <= STALE_THRESHOLD_SECONDS else "stale"


def _live_label(run_dir: Path) -> str:
    """Sufiks label durasi utk run tanpa verdict.json (dipakai page_index &
    page_run): " (live)" bila run_liveness live, else " (stale?)"."""
    return " (live)" if run_liveness(run_dir) == "live" else " (stale?)"


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds >= 60:
        return f"{seconds / 60:.1f}m"
    return f"{int(seconds)}s"


def render_event_line(ev: dict) -> str:
    """Satu event dict -> satu baris ringkas: ts phase event verdict aN detail."""
    ts = str(ev.get("ts") or "-")
    phase = str(ev.get("phase") or "-")
    event = str(ev.get("event") or "-")
    verdict = str(ev.get("verdict") or "-")
    attempt = f"a{ev.get('attempt')}" if ev.get("attempt") is not None else "-"
    detail = ev.get("detail")
    if detail:
        try:
            dtxt = json.dumps(detail, ensure_ascii=False)
        except (TypeError, ValueError):
            dtxt = str(detail)
        if len(dtxt) > 120:
            dtxt = dtxt[:117] + "..."
    else:
        dtxt = ""
    return (f"{ts}  {phase:<9} {event:<5} {verdict:<11} {attempt:<3} "
            f"{dtxt}").rstrip()


# --- rendering HTML ----------------------------------------------------------

_STYLE = """<style>
body{background:#111;color:#ddd;font-family:Consolas,monospace;
     font-size:13px;margin:1em 2em}
a{color:#7bf}
h1,h2{font-size:15px;color:#fff}
pre{background:#000;border:1px solid #333;padding:.6em;overflow-x:auto;
    white-space:pre-wrap}
table{border-collapse:collapse}
td,th{padding:.15em .8em;text-align:left;border-bottom:1px solid #2a2a2a}
.dim{color:#888}
.tabs{margin:.8em 0}
.tabs a{display:inline-block;padding:.35em 1.1em;border:1px solid #333;
        border-bottom:none;margin-right:.3em;text-decoration:none;
        background:#1a1a1a;border-radius:4px 4px 0 0}
.tabs a.active{background:#000;color:#fff;border-color:#555}
.pager{margin:.6em 0}
.pager a{margin-right:1em}
.summary{margin:.6em 0;padding:.5em .8em;border:1px solid #333;
         background:#181818;border-radius:4px;max-width:640px}
.summary p{margin:.2em 0}
.sbar{display:flex;height:10px;background:#333;border-radius:3px;
      overflow:hidden;margin:.45em 0}
.sp{background:#2e7d32}.sf{background:#b03030}.su{background:#666}
.sw{background:#8a6d1a}.sa{background:#7b1fa2}
.summary details{margin-top:.35em}
.summary summary{cursor:pointer;color:#7bf}
.search{margin:.6em 0}
.search input[type=text]{background:#000;color:#ddd;border:1px solid #444;
    border-radius:3px;padding:.3em .5em;font:inherit;width:22em;max-width:80vw}
.search button{background:#1a1a1a;color:#ddd;border:1px solid #444;
    border-radius:3px;padding:.3em .9em;font:inherit;cursor:pointer;
    margin-left:.3em}
.search button:hover{background:#262626}
.search .clear{margin-left:.8em;color:#888;text-decoration:none}
.rfilter{margin:.5em 0;color:#aaa}
.rfilter label{margin-right:.9em;cursor:pointer}
.info-link{color:#7bf;cursor:pointer;text-decoration:underline;margin-left:.4em}
.xbtn{background:none;border:none;color:inherit;font:inherit;cursor:pointer;
      padding:0}
.xbtn:hover{filter:brightness(1.35)}
.copybtn{background:none;border:none;color:#7bf;font:inherit;cursor:pointer;
      padding:0 .35em;opacity:.55}
.copybtn:hover{opacity:1}
.copybtn.ok{color:#4caf50;opacity:1}
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);
    z-index:50;align-items:center;justify-content:center}
.modal-box{background:#181818;border:1px solid #555;border-radius:6px;
    padding:1em 1.4em 1em 1.2em;max-width:560px;max-height:80vh;overflow:auto;
    position:relative}
.modal-x{position:absolute;top:.3em;right:.45em;background:none;border:none;
    color:#aaa;font-size:1.3em;cursor:pointer;line-height:1}
.modal-title{font-weight:bold;color:#fff;margin:0 1.5em .5em 0}
.modal-body{white-space:pre-wrap;color:#ddd;line-height:1.4}
</style>"""


# Modal + JS inline global (dashboard lokal, JS-on diasumsikan): satu overlay
# reusable diisi JS untuk (a) legenda "[info]" dan (b) alasan FAIL/ANOMALY saat
# ikon diklik; plus radio filter baris tabel utama. Tanpa library eksternal.
_MODAL_JS = """
<div id="uiModal" class="modal-overlay" onclick="if(event.target===this)closeModal()">
  <div class="modal-box">
    <button type="button" class="modal-x" onclick="closeModal()">&times;</button>
    <div id="uiModalTitle" class="modal-title"></div>
    <div id="uiModalBody" class="modal-body"></div>
  </div>
</div>
<script>
function closeModal(){document.getElementById('uiModal').style.display='none';}
function _openModal(){document.getElementById('uiModal').style.display='flex';}
function showReason(el){
  document.getElementById('uiModalTitle').textContent=
      'alasan: '+(el.getAttribute('data-case')||'');
  document.getElementById('uiModalBody').textContent=
      el.getAttribute('data-reason')||'(detail tidak terekam)';
  _openModal();
}
function showInfo(){
  document.getElementById('uiModalTitle').textContent='legenda status';
  var b=document.getElementById('legendBody');
  document.getElementById('uiModalBody').innerHTML=b?b.innerHTML:'';
  _openModal();
}
function filterRows(v){
  var rows=document.querySelectorAll('tr[data-status]');
  for(var i=0;i<rows.length;i++){
    var s=rows[i].getAttribute('data-status');
    rows[i].style.display=((v==='All')||(v===s))?'':'none';
  }
}
function _copyFeedback(btn){
  var prev=btn.textContent;
  btn.textContent='✓';
  btn.classList.add('ok');
  setTimeout(function(){btn.textContent=prev;btn.classList.remove('ok');},1000);
}
function _fallbackCopy(text){
  // insecure context (HTTP ke IP LAN non-localhost): clipboard API undefined,
  // pakai textarea sementara + execCommand('copy').
  try{
    var ta=document.createElement('textarea');
    ta.value=text;
    ta.setAttribute('readonly','');
    ta.style.position='fixed';
    ta.style.left='-9999px';
    ta.style.top='0';
    document.body.appendChild(ta);
    ta.select();
    var ok=document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  }catch(e){return false;}
}
function copyCaseJSON(btn){
  var text=btn.getAttribute('data-copy')||'';
  try{
    if(navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(
        function(){_copyFeedback(btn);},
        function(){if(_fallbackCopy(text))_copyFeedback(btn);});
    } else {
      if(_fallbackCopy(text))_copyFeedback(btn);
    }
  }catch(e){
    if(_fallbackCopy(text))_copyFeedback(btn);
  }
}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});
</script>
"""


def _page(title: str, body: str, refresh: bool = False) -> str:
    meta = '<meta http-equiv="refresh" content="3">' if refresh else ""
    return (f"<!doctype html><html><head><meta charset='utf-8'>{meta}"
            f"<title>{html.escape(title)}</title>{_STYLE}</head>"
            f"<body>{body}{_MODAL_JS}</body></html>")


def index_row_verdict(phases: dict, wall) -> tuple[str, str]:
    """(teks verdict, ikon) untuk satu baris tabel index (masukan Mirza
    2026-07-19): fase tunggal tanpa prefix, abort eksplisit, ikon jadi
    kolom sendiri."""
    if not phases:
        return ("abort", "") if wall == "abort" else ("-", "")
    if len(phases) == 1:
        val = next(iter(phases.values()))
        return str(val), verdict_icon(val)
    text = " ".join(f"{k}={v}" for k, v in phases.items())
    vals = list(phases.values())
    if all(v in ("pass", "flip") for v in vals):
        icon = verdict_icon("pass")
    elif any(verdict_icon(v).startswith("❌") for v in vals):
        icon = verdict_icon("fail")
    else:
        icon = ""
    return text, icon


def _verdict_summary(v) -> str:
    """Map fase->verdict jadi teks singkat berikon; non-dict apa adanya."""
    if isinstance(v, dict):
        return " ".join(f"{k}={verdict_icon(val)}{val}"
                        for k, val in v.items()) or "-"
    if v is None:
        return "-"
    return str(v)


PAGE_SIZE = 15


def _search_box(active: str, q: str | None) -> str:
    """Kotak search/filter by nama case (GET form). `tab` dibawa sbg hidden
    field supaya submit tetap di tab aktif; q terisi ulang. Tautan 'hapus'
    muncul saat filter aktif."""
    qval = html.escape(q or "", quote=True)
    clear = ("<a class='clear' href='/?tab=" + urllib.parse.quote(active)
             + "'>&times; hapus filter</a>") if q else ""
    return ("<form class='search' method='get' action='/'>"
            f"<input type='hidden' name='tab' value='{html.escape(active, quote=True)}'>"
            f"<input type='text' name='q' value='{qval}' "
            "placeholder='cari nama case (mis. 15902 atau django-114)' "
            "autocomplete='off'>"
            "<button type='submit'>cari</button>"
            + clear + "</form>")


def _row_status_from_icon(icon: str) -> str:
    """Status baris tabel utama utk data-status (radio filter) dari IKON baris
    (permintaan Mirza 2026-07-21): ✅->PASS, ❌->FAIL, ⏳->WAIT, ⚠️->ANOMALY,
    selain itu "?". Konsisten dgn ikon yg menentukan baris (utk f-* ikon sudah
    = status_icon(case_status), utk r/l diturunkan dari verdict/ikon baris)."""
    if icon.startswith("✅"):
        return "PASS"
    if icon.startswith("❌"):
        return "FAIL"
    if icon.startswith("⏳"):
        return "WAIT"
    if icon.startswith("⚠"):
        return "ANOMALY"
    if icon.startswith("➖"):
        # run tanpa verdict.json yg STALE (dibunuh) — belum resolved & perlu
        # diperiksa, jadi ikut kelompok WAIT (permintaan Mirza 2026-07-22).
        return "WAIT"
    return "?"


def page_index(root: Path, tab: str | None = None, page: int = 1,
               q: str | None = None) -> str:
    parts = ["<h1>gemma-harness log viewer</h1>",
             f"<p class='dim'>root: {html.escape(str(root))}</p>"]
    campaigns = order_campaigns(with_stage_tabs(list_campaigns(root)))
    if not campaigns:
        parts.append("<p>(belum ada campaign)</p>")
        return _page("log viewer", "".join(parts))

    active = tab if tab in campaigns else campaigns[0]
    # q dibawa lintas tab supaya filter berlaku di ketiga tab (permintaan Mirza)
    qsuffix = ("&q=" + urllib.parse.quote(q)) if q else ""
    tab_links = []
    for camp in campaigns:
        cls = " class='active'" if camp == active else ""
        tab_links.append(
            f"<a{cls} href='/?tab={urllib.parse.quote(camp)}{qsuffix}'>"
            f"{html.escape(campaign_label(camp))}</a>")
    parts.append("<div class='tabs'>" + "".join(tab_links) + "</div>")
    parts.append(_search_box(active, q))

    runs = sort_runs_desc(list_runs(root / active), root / active)
    if not runs:
        parts.append("<p class='dim'>(belum ada run)</p>")
        return _page("log viewer", "".join(parts))

    # filter by nama case SEBELUM ringkasan + paginasi -> nyaring lintas
    # semua halaman, bukan cuma halaman aktif (permintaan Mirza 2026-07-21)
    runs = filter_runs_by_case(runs, q)
    if q:
        parts.append(f"<p class='dim'>filter case: "
                     f"<b>{html.escape(q)}</b> &middot; {len(runs)} run cocok"
                     "</p>")
    if not runs:
        parts.append("<p class='dim'>(tidak ada case cocok dengan filter)</p>")
        return _page("log viewer", "".join(parts))

    # panel ringkasan per tahapan: dihitung dari run (ter)filter, bukan
    # halaman ini — konsisten dgn tabel di bawahnya
    summary = stage_summary(root / active, active, runs)
    parts.append(render_stage_summary(summary))
    # alasan per-CASE (kategori+reasons dari run yang dipilih summary) ->
    # dipakai modal saat ikon FAIL/ANOMALY di tabel utama diklik
    reason_by_case = {i["case"]: i for i in summary["items"]}

    # radio filter baris tabel utama (All/PASS/FAIL) — client-side JS
    # (filterRows) berlaku otomatis di ketiga tab (permintaan Mirza 2026-07-21)
    parts.append(
        "<div class='rfilter'>filter: "
        "<label><input type='radio' name='rowfilter' value='All' checked "
        "onchange=\"filterRows('All')\"> All</label>"
        "<label><input type='radio' name='rowfilter' value='PASS' "
        "onchange=\"filterRows('PASS')\"> PASS</label>"
        "<label><input type='radio' name='rowfilter' value='FAIL' "
        "onchange=\"filterRows('FAIL')\"> FAIL</label></div>")

    page_runs, total_pages = paginate(runs, page, PAGE_SIZE)
    rows = []
    for r in page_runs:
        rid = r["run_id"]
        vpath = root / active / rid / "verdict.json"
        vtext, icon = "-", ""
        if vpath.is_file():
            try:
                vj = json.loads(vpath.read_text(encoding="utf-8"))
                phases = {k: (p or {}).get("verdict")
                          for k, p in (vj.get("phases") or {}).items()}
                vtext, icon = index_row_verdict(phases, vj.get("wall"))
                vtext, icon = merge_gold_verdict(vtext, icon, active,
                                                 root / active / rid)
                if active.startswith("f-"):
                    # ikon baris disinkronkan ke status 2-lapisan (spec §6)
                    # — teks verdict TETAP vonis L1 produk apa adanya
                    # (permintaan Mirza: viewer verify-fail jangan lagi ✅).
                    two_status = case_status(active, root / active / rid)
                    icon = status_icon(two_status["status"])
            except (ValueError, OSError, AttributeError):
                vtext = "(verdict.json rusak)"
        href = ("/run?c=" + urllib.parse.quote(active)
                + "&r=" + urllib.parse.quote(rid))
        dur = fmt_duration(run_duration_seconds(root / active / rid))
        if not vpath.is_file():
            # run tanpa verdict.json: bedakan yang masih aktif (mtime
            # console.log/events.jsonl baru) dari yang beku (dibunuh) —
            # jangan lagi cap semuanya "(live)" selamanya.
            dur += _live_label(root / active / rid)
            # ikon marker STALE (dibunuh/ditinggalkan) supaya beda secara
            # visual dari run yg benar-benar jalan (yg tetap kosong) & dari
            # pass/fail (✅/❌) — permintaan Mirza 2026-07-22. Live: kosong.
            if run_liveness(root / active / rid) == "stale":
                icon = "➖ "
        turns = run_turns(root / active / rid)
        case_id, rerun = split_run_id(rid)
        # status baris utk data-status (radio filter) & modal alasan: dari
        # ikon baris itu sendiri (✅->PASS, ❌->FAIL, ⏳->WAIT, ⚠️->ANOMALY);
        # utk f-* ikon sudah = status_icon(case_status), jadi konsisten.
        row_status = _row_status_from_icon(icon)
        if row_status in ("FAIL", "ANOMALY"):
            item = reason_by_case.get(case_id)
            rtext = _fail_reason_text(item) if item else "(detail tidak terekam)"
            icon_cell = (
                "<button type='button' class='xbtn' "
                f"data-case=\"{html.escape(case_id, quote=True)}\" "
                f"data-reason=\"{html.escape(rtext, quote=True)}\" "
                f"onclick='showReason(this)'>{icon}</button>")
        else:
            icon_cell = icon
        # tombol copy-to-clipboard di sebelah nama case: menyalin string JSON
        # {"case": "<id>", "phase": "<R|L|FV>", "run": "<rN>"} — phase dari
        # kampanye aktif, run = rerun baris ini (split_run_id di atas).
        copy_json = copy_case_json(case_id, active, rerun)
        copy_btn = (
            "<button type='button' class='copybtn' title='copy JSON' "
            f"data-copy=\"{html.escape(copy_json, quote=True)}\" "
            "onclick='copyCaseJSON(this)'>📋</button>")
        rows.append(
            f"<tr data-status=\"{html.escape(row_status, quote=True)}\">"
            f"<td>{html.escape(case_id)} {copy_btn}</td>"
            f"<td><a href='{href}'>{html.escape(rerun or rid)}</a></td>"
            f"<td>{icon_cell}</td>"
            f"<td>{html.escape(vtext)}</td>"
            f"<td class='dim'>{html.escape(dur)}</td>"
            f"<td class='dim'>{turns if turns is not None else '-'}</td>"
            f"<td class='dim'>"
            f"{html.escape(run_started_str(root / active / rid))}</td></tr>")
    parts.append("<table><tr><th>case</th><th>run</th><th></th><th>verdict</th>"
                 "<th>durasi</th><th>turns</th><th>mulai</th></tr>"
                 + "".join(rows) + "</table>")

    if total_pages > 1:
        nav = []
        page = max(1, min(page, total_pages))
        base = ("/?tab=" + urllib.parse.quote(active) + qsuffix + "&page=")
        if page > 1:
            nav.append(f"<a href='{base}{page - 1}'>&laquo; lebih baru</a>")
        nav.append(f"<span class='dim'>hal {page}/{total_pages}</span>")
        if page < total_pages:
            nav.append(f"<a href='{base}{page + 1}'>lebih lama &raquo;</a>")
        parts.append("<div class='pager'>" + " ".join(nav) + "</div>")
    return _page("log viewer", "".join(parts))


def page_run(root: Path, campaign: str, run_id: str, n: int) -> str:
    run_dir = root / campaign / run_id
    title = f"{campaign} / {run_id}"
    dur = fmt_duration(run_duration_seconds(run_dir))
    if not (run_dir / "verdict.json").is_file():
        dur += _live_label(run_dir)
    parts = [f"<p><a href='/'>&larr; index</a></p>"
             f"<h1>{html.escape(title)}</h1>"
             f"<p class='dim'>durasi: {html.escape(dur)}</p>"]

    vpath = run_dir / "verdict.json"
    if vpath.is_file():
        try:
            vj = json.loads(vpath.read_text(encoding="utf-8"))
            summ = _verdict_summary({k: (p or {}).get("verdict")
                                     for k, p in (vj.get("phases") or {}).items()})
            parts.append(f"<p>verdict: {html.escape(summ)} | "
                         f"wall: {html.escape(str(vj.get('wall')))}</p>")
        except (ValueError, OSError, AttributeError):
            parts.append("<p class='dim'>verdict.json rusak — isi mentah:</p>"
                         "<pre>" + html.escape(
                             vpath.read_text(encoding="utf-8",
                                             errors="replace")) + "</pre>")
    else:
        parts.append("<p class='dim'>(verdict.json belum ada — run berjalan?)"
                     "</p>")

    if campaign.startswith("f-"):
        sw = read_swebench_eval(run_dir)
        two_status = case_status(campaign, run_dir).get("status")
        parts.append("<h2>VERIFY (SWE-bench)</h2>")
        if two_status == "ANOMALY":
            parts.append("<p>⚠️ ANOMALY: product FAIL tapi "
                         "SWE-bench resolved — autopsi manual</p>")
        if sw is None:
            if two_status == "WAIT":
                parts.append(
                    "<p class='dim'>product-pass, menunggu VERIFY — "
                    "swebench_eval.json belum ada (jalankan "
                    "python -m eval.swebench_checker)</p>")
            else:
                parts.append(
                    "<p class='dim'>product FAIL — VERIFY tidak "
                    "dijalankan</p>")
        else:
            ok = "✅" if sw.get("resolved") else "❌"
            parts.append(
                f"<p>resolved: {ok} {html.escape(str(sw.get('resolved')))} | "
                f"apply: {html.escape(str(sw.get('patch_successfully_applied')))} | "
                f"F2P lulus {len(sw.get('f2p_passed') or [])} / gagal "
                f"{len(sw.get('f2p_failed') or [])} | P2P lulus "
                f"{sw.get('p2p_passed_count', '?')} / regresi "
                f"{len(sw.get('p2p_failed') or [])}</p>")
            for label, key in (("F2P gagal", "f2p_failed"),
                               ("regresi P2P", "p2p_failed")):
                if sw.get(key):
                    items = "".join(f"<li>{html.escape(str(t))}</li>"
                                    for t in sw[key])
                    parts.append(f"<p>{label}:</p><ul>{items}</ul>")
        gpath = run_dir / "gold_eval.json"
        parts.append("<h2>gold-match (advisory)</h2>")
        if gpath.is_file():
            try:
                g = json.loads(gpath.read_text(encoding="utf-8"))
                parts.append(
                    f"<p class='dim'>file_match: {g.get('file_match')} | "
                    f"line_overlap: {g.get('line_overlap')} | touched: "
                    f"{html.escape(', '.join(g.get('touched_files') or []))} "
                    f"vs gold: "
                    f"{html.escape(', '.join(g.get('gold_files') or []))}</p>")
            except (OSError, ValueError):
                parts.append("<p class='dim'>gold_eval.json rusak</p>")
        else:
            parts.append("<p class='dim'>(gold_eval.json belum ada)</p>")
        swlog = tail_lines(run_dir / "files" / "swebench_test_output.log", n)
        if swlog:
            parts.append(f"<h2>swebench_test_output.log (tail {n})</h2>")
            parts.append("<pre>" + html.escape("\n".join(swlog)) + "</pre>")

    parts.append(f"<h2>events.jsonl (tail {n})</h2>")
    ev_lines = tail_lines(run_dir / "events.jsonl", n)
    if not ev_lines:
        parts.append("<p class='dim'>(events.jsonl belum ada / kosong)</p>")
    else:
        rendered = []
        for line in ev_lines:
            try:
                obj = json.loads(line)
                rendered.append(render_event_line(obj)
                                if isinstance(obj, dict) else line)
            except ValueError:
                rendered.append(line)  # baris rusak: tampil apa adanya
        parts.append("<pre>" + html.escape("\n".join(rendered)) + "</pre>")

    parts.append(f"<h2>console.log (tail {n})</h2>")
    con_lines = tail_lines(run_dir / "console.log", n)
    if not con_lines:
        parts.append("<p class='dim'>(console.log belum ada / kosong)</p>")
    else:
        parts.append("<pre>" + html.escape("\n".join(con_lines)) + "</pre>")

    return _page(title, "".join(parts), refresh=True)


# --- HTTP layer ---------------------------------------------------------------

def make_handler(root: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send_html(self, body: str, status: int = 200) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 (nama API stdlib)
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if parsed.path == "/":
                tab = (qs.get("tab") or [None])[0]
                if tab is not None and not validate_name(tab):
                    tab = None
                try:
                    page = int((qs.get("page") or ["1"])[0])
                except ValueError:
                    page = 1
                # q = search bebas (nama case); tak dipakai sbg path -> cukup
                # di-escape saat render. Dipangkas agar tak jadi query raksasa.
                q = (qs.get("q") or [None])[0]
                if q is not None:
                    q = q[:100]
                self._send_html(page_index(root, tab=tab, page=page, q=q))
            elif parsed.path == "/run":
                camp = (qs.get("c") or [""])[0]
                rid = (qs.get("r") or [""])[0]
                if not (validate_name(camp) and validate_name(rid)):
                    self._send_html(_page("400", "<p>parameter c/r tidak sah"
                                          "</p>"), 400)
                    return
                try:
                    nval = int((qs.get("n") or [str(DEFAULT_TAIL)])[0])
                except ValueError:
                    nval = DEFAULT_TAIL
                nval = max(1, min(nval, 5000))
                self._send_html(page_run(root, camp, rid, nval))
            else:
                self._send_html(_page("404", "<p>tidak ditemukan</p>"), 404)

        def log_message(self, fmt, *args):  # senyap di terminal
            pass

    return Handler


def main(argv: list[str] | None = None) -> None:
    default_root = Path(__file__).resolve().parents[1].parent / "artifacts"
    ap = argparse.ArgumentParser(description="UI log viewer harness SWE-bench")
    ap.add_argument("--root", type=Path, default=default_root,
                    help=f"direktori artifacts (default: {default_root})")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default="127.0.0.1",
                    help="alamat bind (default 127.0.0.1 = localhost saja; "
                         "pakai 0.0.0.0 agar bisa diakses dari komputer lain)")
    args = ap.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port),
                                 make_handler(args.root.resolve()))
    print(f"log viewer: http://{args.host}:{args.port}/  "
          f"(root={args.root.resolve()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
