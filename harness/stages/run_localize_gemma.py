"""Driver stage LOCALIZE untuk Gemma (dev-run v0).

Sama polanya dengan run_reproduce_gemma: loop teks protokol fenced-block.
Perbedaan: input = artefak REPRODUCE beku (repro.md + repro.py) yang
di-install driver ke container; artefak final = localize.md; guard tulis-file:
`file:` HANYA boleh menulis di bawah /testbed/.pipe/ (probe) — repo read-only.

Pemakaian (dari root main):
    python harness/stages/run_localize_gemma.py --case django__django-11422
        --rerun 2 --image ghcr.io/... --input-files <dir files run REPRODUCE>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from pathlib import Path

from harness.emit import Emitter
from harness.stages.gemma_protocol import (done_rejection_localize, has_done,
                                           no_action_feedback, parse_actions)
from harness.stages.localize_gates import (MAX_SPAN,
                                           audit_candidate_evidence,
                                           candidates_done_error,
                                           demote_mismatched_candidates,
                                           evaluate_localize_gates,
                                           parse_candidates_md,
                                           parse_localize_md,
                                           reorder_candidates_text)
from harness.stages.localize_trace import (candidates_pool_error,
                                           format_trace_pool_message,
                                           run_trace)

# Bentuk aksi sah untuk pengingat no-action (R3): dikonsumsi no_action_feedback.
_ACTION_FORMS = (
    "```bash                       -> run a shell command\n"
    "```file:/testbed/.pipe/<path> -> write that file with the block's content\n"
    "```localize.md                -> submit the localize.md artifact")

PROTOCOL_NOTE = """
## How to work (action protocol — MANDATORY)

You work through action blocks in your replies. One reply may contain several
blocks; they are executed in order and I send the results back to you.

1. Run a shell command in the /testbed sandbox (read code, grep, run the
   repro/probe):
```bash
<command>
```
2. Write a probe script or note in your workspace /testbed/.pipe/:
```file:/testbed/.pipe/probe.py
<file content>
```
3. Submit the candidates you weighed (per the contract — at least two,
   at most three, from different files):
```candidates.md
<candidates.md content>
```
4. Submit the final localize.md artifact (6 slots per the contract):
```localize.md
<localize.md content>
```
Close with a single line containing exactly:
DONE
Declare DONE only after you have explored the code and your evidence points
at the mechanism site.

Work step by step: act, wait for my output, then take the next step based on
what you observed. Keep prose minimal; focus on the next action.
"""


def chat(endpoint: str, model: str, messages: list[dict], timeout: int = 600) -> str:
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 2048,
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    return data["choices"][0]["message"]["content"] or ""


def docker_exec(container: str, cmd: str, timeout: int = 180) -> tuple[str, int]:
    p = subprocess.run(
        ["docker", "exec", container, "bash", "-lc", cmd],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    return (p.stdout or "") + (p.stderr or ""), p.returncode


def docker_write_file(container: str, path: str, body: str) -> None:
    # Bytes mentah, BUKAN text=True (pelajaran r15, diport dari driver R/F):
    # mode teks Windows menerjemahkan \n -> \r\n saat menulis ke pipe;
    # kontrak §2: byte \r di file tulisan model adalah BUG.
    data = body.replace("\r\n", "\n").encode("utf-8")
    subprocess.run(
        ["docker", "exec", "-i", container, "bash", "-lc",
         f"mkdir -p $(dirname '{path}') && cat > '{path}'"],
        input=data, check=True, timeout=60,
    )


def tail(s: str, n: int = 4000) -> str:
    return s if len(s) <= n else "[...dipotong...]\n" + s[-n:]


def localize_range_error(container: str, localize_text: str) -> str | None:
    """Lever L-a (baseline 12747 l-dev r1-r3): penahan DONE atas localize.md.

    Kelas kegagalan: rentang baris melewati akhir file (380-450 pada file
    445 baris; juga 713-844) — gate L1 memvonisnya SETELAH run selesai,
    driver menerima DONE tanpa cek -> nol retry, run hangus. Di sini vonis
    yang SAMA (evaluate_localize_gates: format slot, start>=1, start<=end,
    span<=MAX_SPAN, end<=EOF) dihitung SAAT DONE supaya model dapat retry.
    Panjang file diukur `wc -l` di container kerja (pola run_localize_gates);
    fail-closed bila file tak terbaca. None = localize.md lolos.
    """
    try:
        slots = parse_localize_md(localize_text)
    except ValueError as e:
        return (f"Not done yet: your localize.md is malformed ({e}). "
                "Submit a corrected ```localize.md block with all six "
                "slots, then declare DONE again.")
    target = slots["file"].lstrip("/")
    out, code = docker_exec(
        container,
        f"test -f '/testbed/{target}' && wc -l < '/testbed/{target}'")
    line_count: int | None = None
    if code == 0:
        try:
            line_count = int(out.strip())
        except ValueError:
            line_count = None
    if line_count is None:
        return (f"Not done yet: the file {slots['file']} named in your "
                "localize.md could not be read in the repository, so your "
                "lines range cannot be verified. Point file: at a real "
                "repository file path, then declare DONE again.")
    r = evaluate_localize_gates(localize_text, file_exists=True,
                                file_line_count=line_count)
    if r.verdict == "pass":
        return None
    start, end = slots["lines"]
    return ("Not done yet: your localize.md failed a mechanical check: "
            + "; ".join(r.failures) + ". "
            f"The file {slots['file']} has {line_count} lines and your "
            f"lines slot says {start}-{end}. Re-open the file, point "
            "lines: at a range that lies inside it (at most "
            f"{MAX_SPAN} lines wide), and submit a corrected "
            "```localize.md block, then declare DONE again.")


def audit_candidates_evidence(container: str, candidates_text: str
                              ) -> tuple[str, list[dict] | None]:
    """Lever N2 (mandat Mirza 2026-07-22): audit konsistensi evidence<->file.

    Bukti 12184: kandidat #1 django/urls/base.py dgn evidence menyebut
    `URLPattern.resolve` — simbol itu tidak ada di base.py (adanya di
    resolvers.py, kandidat #2) -> FIX dipenjara 40 turn di file salah.
    Di sini, SEBELUM candidates.md dibekukan, simbol beridiom kode pada
    evidence tiap kandidat dicek keberadaannya di isi file yang diklaim
    (dibaca lewat jalur read-only docker_exec yang sudah dipakai driver);
    simbol hilang -> evidence_mismatch -> DEMOSI ke ekor shortlist. Demosi
    hanya mengubah urutan attempt FIX — kandidat tidak pernah dihapus, dan
    format candidates.md tetap sesuai kontrak. File tak terbaca -> tidak
    didemosi (gagal-aman, prinsip prune).

    Keterbatasan sadar (varian 15388): evidence yang salah-atribusi
    MEKANISME pada file yang BENAR lolos audit ini — simbolnya memang ada
    di file. Cek simbol hanya menangkap varian salah-file (12184).

    Return (teks_final, rows autopsi); rows None bila candidates.md tak
    terparse (bentuk salah = urusan cek DONE/gate, bukan audit ini).
    """
    try:
        cands = parse_candidates_md(candidates_text)
    except ValueError:
        return candidates_text, None
    audits: list[dict] = []
    for cand in cands:
        target = cand["file"].lstrip("/")
        out, code = docker_exec(container, f"cat '/testbed/{target}'")
        audits.append(audit_candidate_evidence(
            cand["evidence"], out if code == 0 else None))
    order = demote_mismatched_candidates(audits)
    rows = []
    for new_rank, old_i in enumerate(order, start=1):
        a = audits[old_i]
        rows.append({"candidate": old_i + 1, "file": cands[old_i]["file"],
                     "symbols": a["symbols"], "missing": a["missing"],
                     "checked": a["checked"],
                     "evidence_mismatch": a["evidence_mismatch"],
                     "new_rank": new_rank})
    rows.sort(key=lambda r: r["candidate"])
    if order != list(range(len(cands))):
        candidates_text = reorder_candidates_text(candidates_text, order)
    return candidates_text, rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--rerun", type=int, required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--input-files", required=True,
                    help="dir files/ run REPRODUCE (berisi repro.py + repro.md)")
    ap.add_argument("--campaign", default="l-dev")
    ap.add_argument("--artifacts", default="../artifacts")
    ap.add_argument("--problem-file", required=True)
    ap.add_argument("--endpoint", default="http://10.8.0.86:8000/v1")
    ap.add_argument("--model", default="google/gemma-4-31B-it")
    ap.add_argument("--max-turns", type=int, default=40)
    args = ap.parse_args()

    problem = Path(args.problem_file).read_text(encoding="utf-8")
    input_dir = Path(args.input_files)
    repro_md = (input_dir / "repro.md").read_text(encoding="utf-8")
    repro_py = (input_dir / "repro.py").read_text(encoding="utf-8")
    contract = Path(__file__).with_name("localize_prompt.md").read_text(encoding="utf-8")

    em = Emitter(args.artifacts, args.campaign, args.case, args.rerun)
    console = em.run_dir / "console.log"

    def log(line: str) -> None:
        with open(console, "a", encoding="utf-8", newline="\n") as f:
            f.write(line.rstrip("\n") + "\n")

    container = f"gemma-work-{args.campaign}-{args.case}-r{args.rerun}"
    subprocess.run(["docker", "rm", "-f", container], capture_output=True)
    subprocess.run(["docker", "run", "-d", "--name", container, args.image,
                    "sleep", "infinity"], check=True, capture_output=True)
    docker_write_file(container, "/testbed/.pipe/repro.py", repro_py)
    # LV-09 (gap kembar sisi L): repro ber-`from pipe_runtime import App` harus
    # bisa dijalankan model di dunia kerja L juga — kirim runtime-nya bila ada.
    rt_path = input_dir / "pipe_runtime.py"
    if rt_path.is_file():
        docker_write_file(container, "/testbed/.pipe/pipe_runtime.py",
                          rt_path.read_text(encoding="utf-8"))
    # Lever L#4 (helper probe, autopsi 11964): boilerplate framework utk
    # probe ber-Model dipindah ke modul yang di-ship — kelas probe-crash
    # app-registry mati by construction.
    probe_rt = Path(__file__).with_name("probe_runtime.py").read_text(
        encoding="utf-8")
    docker_write_file(container, "/testbed/.pipe/probe_runtime.py", probe_rt)
    log(f"[driver] container {container} started; input repro installed "
        f"from {input_dir}; probe_runtime shipped")

    em.run_start()

    # Lever L#3 (trace-injection): repro dieksekusi di container SEGAR di
    # bawah coverage trace; pool file repo yang tereksekusi diinject ke
    # pesan user pertama + enforce candidates ⊆ pool. Gagal trace = abort
    # (lever wajib hidup, bukan fail-open senyap).
    try:
        trace_pool, _trace_raw = run_trace(args.image,
                                           str(input_dir.resolve()))
    except Exception as e:
        em.event("localize", "abort",
                 detail={"why": f"trace-injection run failed: {e}"})
        log(f"[driver] trace run failed: {e}")
        subprocess.run(["docker", "stop", container], capture_output=True)
        return 1
    pool_set = {p.lstrip("/") for p in trace_pool}
    (em.run_dir / "files" / "trace_pool.json").write_text(
        json.dumps(trace_pool, ensure_ascii=False, indent=0) + "\n",
        encoding="utf-8", newline="\n")
    log(f"[driver] trace pool: {len(trace_pool)} repo files executed "
        f"during repro (files/trace_pool.json)")

    em.event("localize", "enter",
             budget={"msg_used": 0, "msg_limit": args.max_turns},
             detail={"model": args.model, "driver": "run_localize_gemma-v2",
                     "input_files": str(input_dir),
                     "trace_pool_files": len(trace_pool)})

    system = contract + PROTOCOL_NOTE
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content":
         "PROBLEM STATEMENT:\n" + problem +
         "\n\nREPRODUCE ARTIFACTS (frozen input, already gate-approved):\n" +
         repro_md +
         "\nThe repro script is installed at /testbed/.pipe/repro.py.\n\n" +
         format_trace_pool_message(trace_pool) +
         "\n\nStart working now. The /testbed sandbox is at the base commit."},
    ]

    attempt = 1
    localize_md: str | None = None
    candidates_md: str | None = None
    ran_any_bash = False
    done = False

    def candidates_error_now() -> str | None:
        """Cek mekanis enumerasi (Lever L#2): bentuk (pure) + keberadaan
        file kandidat di repo container."""
        loc_file: str | None = None
        if localize_md is not None:
            try:
                loc_file = parse_localize_md(localize_md)["file"]
            except ValueError:
                loc_file = None  # format salah — gate L1 yang memvonis
        err = candidates_done_error(candidates_md, loc_file)
        if err is not None:
            return err
        cands = parse_candidates_md(candidates_md)
        for cand in cands:
            target = cand["file"].lstrip("/")
            _, code = docker_exec(container, f"test -f '/testbed/{target}'")
            if code != 0:
                return (f"Not done yet: candidate file {cand['file']!r} does "
                        f"not exist in the repository — every candidate must "
                        f"be a real file.")
        # Lever L#3: kandidat wajib anggota pool file yang tereksekusi
        # saat repro (subset check mekanis).
        return candidates_pool_error([c["file"] for c in cands], pool_set)
    for turn in range(1, args.max_turns + 1):
        try:
            reply = chat(args.endpoint, args.model, messages)
        except Exception as e:
            log(f"[driver] chat error: {e}; retrying once")
            reply = chat(args.endpoint, args.model, messages)
        messages.append({"role": "assistant", "content": reply})
        log(f"[gemma t{turn}] {reply}")

        actions = parse_actions(reply)
        feedback_parts: list[str] = []
        for act in actions:
            if act.kind == "file":
                if not act.arg.startswith("/testbed/.pipe/"):
                    attempt += 1
                    em.event("localize", "retry", attempt=attempt,
                             budget={"msg_used": turn,
                                     "msg_limit": args.max_turns},
                             detail={"why": ("write outside workspace "
                                             f"rejected: {act.arg}")})
                    log(f"[driver] rejected write outside workspace: {act.arg}")
                    feedback_parts.append(
                        f"Your writable workspace is /testbed/.pipe/ — put "
                        f"{Path(act.arg).name} there instead.")
                    continue
                docker_write_file(container, act.arg, act.body + "\n")
                log(f"[driver] wrote {act.arg} ({len(act.body)} chars)")
                feedback_parts.append(f"OK: file {act.arg} written.")
            elif act.kind == "bash":
                ran_any_bash = True
                out, code = docker_exec(container, act.body)
                log(f"[exec] $ {act.body}\n{tail(out, 2000)}\n[exit {code}]")
                feedback_parts.append(f"OUTPUT (exit {code}):\n{tail(out)}")
            elif act.kind == "localize.md":
                localize_md = act.body
                log("[driver] localize.md candidate received")
                feedback_parts.append("OK: localize.md received.")
            elif act.kind == "candidates.md":
                candidates_md = act.body
                log("[driver] candidates.md received")
                feedback_parts.append("OK: candidates.md received.")

        if has_done(reply):
            reason = done_rejection_localize(
                has_localize_md=localize_md is not None,
                ran_any_bash=ran_any_bash,
                candidates_error=candidates_error_now(),
                localize_error=(None if localize_md is None else
                                localize_range_error(container, localize_md)))
            if reason is not None:
                attempt += 1
                # Telemetri kaya (permintaan Mirza 2026-07-19; pelajaran
                # Prinsip Stabilisasi §5): alasan VERBATIM + posisi artefak
                # — autopsi tanpa rekonstruksi console.
                em.event("localize", "retry", attempt=attempt,
                         budget={"msg_used": turn, "msg_limit": args.max_turns},
                         detail={"why": f"done-rejected: {reason}",
                                 "has_localize_md": localize_md is not None,
                                 "has_candidates_md": candidates_md is not None,
                                 "ran_any_bash": ran_any_bash})
                log(f"[driver] DONE rejected: {reason}")
                feedback_parts.append(reason)
            else:
                done = True
                log(f"[driver] DONE at turn {turn}")
                break

        if not actions and not feedback_parts:
            feedback_parts.append(no_action_feedback(reply, _ACTION_FORMS))
        messages.append({"role": "user", "content": "\n\n".join(feedback_parts)})

    files_dir = em.run_dir / "files"
    if localize_md is not None:
        (files_dir / "localize.md").write_text(localize_md + "\n",
                                               encoding="utf-8", newline="\n")
        log("[driver] files/localize.md written")
    if candidates_md is not None:
        # Lever N2: audit evidence<->file sebelum shortlist dibekukan;
        # container kerja masih hidup di titik ini (stop baru di bawah).
        candidates_md, audit_rows = audit_candidates_evidence(
            container, candidates_md)
        if audit_rows is not None:
            (files_dir / "evidence_audit.json").write_text(
                json.dumps(audit_rows, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8", newline="\n")
            n_mismatch = sum(1 for r in audit_rows
                             if r["evidence_mismatch"])
            em.event("localize", "evidence-audit",
                     detail={"rows": audit_rows,
                             "mismatch_count": n_mismatch})
            log(f"[driver] audit evidence N2: {n_mismatch} dari "
                f"{len(audit_rows)} kandidat evidence_mismatch "
                "(files/evidence_audit.json)")
        (files_dir / "candidates.md").write_text(candidates_md + "\n",
                                                 encoding="utf-8", newline="\n")
        log("[driver] files/candidates.md written")
    (files_dir / "input-repro.md").write_text(repro_md, encoding="utf-8",
                                              newline="\n")

    subprocess.run(["docker", "stop", container], capture_output=True)
    log(f"[driver] container {container} stopped; done={done}, turns={turn}")
    print(json.dumps({"done": done, "turns": turn,
                      "has_localize_md": localize_md is not None}))
    return 0


if __name__ == "__main__":
    main()
