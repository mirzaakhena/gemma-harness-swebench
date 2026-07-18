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
</style>"""


def _page(title: str, body: str, refresh: bool = False) -> str:
    meta = '<meta http-equiv="refresh" content="3">' if refresh else ""
    return (f"<!doctype html><html><head><meta charset='utf-8'>{meta}"
            f"<title>{html.escape(title)}</title>{_STYLE}</head>"
            f"<body>{body}</body></html>")


def _verdict_summary(v) -> str:
    """Map fase->verdict jadi teks singkat; non-dict tampil apa adanya."""
    if isinstance(v, dict):
        return " ".join(f"{k}={val}" for k, val in v.items()) or "-"
    if v is None:
        return "-"
    return str(v)


def page_index(root: Path) -> str:
    parts = ["<h1>gemma-harness log viewer</h1>",
             f"<p class='dim'>root: {html.escape(str(root))}</p>"]
    campaigns = list_campaigns(root)
    if not campaigns:
        parts.append("<p>(belum ada campaign)</p>")
    for camp in campaigns:
        parts.append(f"<h2>{html.escape(camp)}</h2>")
        runs = list_runs(root / camp)
        if not runs:
            parts.append("<p class='dim'>(belum ada run)</p>")
            continue
        rows = []
        for r in runs:
            rid = r["run_id"]
            # verdict.json lebih final daripada baris end runs.jsonl
            verdict = r["verdict"]
            wall = r.get("wall")
            vpath = root / camp / rid / "verdict.json"
            if vpath.is_file():
                try:
                    vj = json.loads(vpath.read_text(encoding="utf-8"))
                    verdict = {k: (p or {}).get("verdict")
                               for k, p in (vj.get("phases") or {}).items()}
                    wall = vj.get("wall")
                except (ValueError, OSError, AttributeError):
                    verdict = "(verdict.json rusak)"
            href = ("/run?c=" + urllib.parse.quote(camp)
                    + "&r=" + urllib.parse.quote(rid))
            rows.append(
                f"<tr><td><a href='{href}'>{html.escape(rid)}</a></td>"
                f"<td>{html.escape(_verdict_summary(verdict))}</td>"
                f"<td class='dim'>{html.escape(str(wall) if wall else '')}"
                f"</td></tr>")
        parts.append("<table><tr><th>run</th><th>verdict</th><th>wall</th>"
                     "</tr>" + "".join(rows) + "</table>")
    return _page("log viewer", "".join(parts))


def page_run(root: Path, campaign: str, run_id: str, n: int) -> str:
    run_dir = root / campaign / run_id
    title = f"{campaign} / {run_id}"
    parts = [f"<p><a href='/'>&larr; index</a></p>"
             f"<h1>{html.escape(title)}</h1>"]

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
                self._send_html(page_index(root))
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
    args = ap.parse_args(argv)

    server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                 make_handler(args.root.resolve()))
    print(f"log viewer: http://127.0.0.1:{args.port}/  "
          f"(root={args.root.resolve()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
