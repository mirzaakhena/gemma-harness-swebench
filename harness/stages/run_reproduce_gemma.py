"""Driver stage REPRODUCE untuk Gemma (dev-run v0).

Loop teks: kirim kontrak stage + problem statement ke endpoint OpenAI-compatible
(vLLM), parse aksi fenced-block (gemma_protocol), eksekusi di container docker
kerja, umpankan output balik. Telemetri via harness.emit; console.log
di-append tiap langkah. Driver TIDAK memvonis: event `exit` + verdict.json
ditulis harness setelah gate mekanis terpisah.

Pemakaian (dari root main):
    python harness/stages/run_reproduce_gemma.py --case django__django-11422
        --rerun 2 --image ghcr.io/... [--max-turns 40]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from pathlib import Path

from harness.emit import Emitter
from harness.stages.gemma_protocol import (done_rejection_reason, has_done,
                                           observable_rejection,
                                           parse_actions,
                                           parse_pass_observable)
from harness.stages.reproduce_gates import compose_repro_md

PROTOCOL_NOTE = """
## How to work (action protocol — MANDATORY)

You work through action blocks in your replies. One reply may contain several
blocks; they are executed in order and I send the results back to you.

1. Run a shell command in the /testbed sandbox:
```bash
<command>
```
2. Write/overwrite a file in the sandbox:
```file:/testbed/.pipe/repro.py
<full file content>
```
3. Submit the final repro.md artifact (the lines listed in the contract):
```repro.md
<repro.md content>
```
Close with a single line containing exactly:
DONE
Declare DONE only after you have run repro.py, seen REPRO_STATUS: FAIL in its
output, and submitted the repro.md block.

Work step by step: act, wait for my output, then take the next step based on
what you observed. Keep prose minimal; focus on the next action.
"""

SELF_CHECK_MSG = """Final check before your DONE is accepted. Answer both,
quoting evidence:

1. Quote the exact code from the repository source (file + line) that will
   produce your PASS observable once the bug is fixed. If you cannot quote
   it, your PASS condition is a guess — read the source first (open the file
   with a bash action and look at the real lines), then revise your script.
   Close your answer with one line in this exact form:
   PASS_OBSERVABLE: <the exact literal string your script matches on to decide PASS>
2. Show that your script exercises the same scenario the issue describes:
   name the entry point / command the user runs in the issue, and point to
   the line in YOUR script that runs that same path. If your script builds
   the state by hand instead, revise it to run the real path.

If both answers hold, declare DONE again. Otherwise revise your script,
re-run it to see REPRO_STATUS: FAIL, then declare DONE."""


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


def _as_text(s) -> str:
    if s is None:
        return ""
    if isinstance(s, bytes):
        return s.decode("utf-8", errors="replace")
    return s


def docker_exec(container: str, cmd: str, timeout: int = 180) -> tuple[str, int]:
    try:
        p = subprocess.run(
            ["docker", "exec", container, "bash", "-lc", cmd],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        return (p.stdout or "") + (p.stderr or ""), p.returncode
    except subprocess.TimeoutExpired as e:
        # Pelajaran r7: repro.py yang hang (mis. menunggu runserver tanpa
        # batas) tidak boleh membunuh driver. Restart container membersihkan
        # proses background yatim; isi disk /testbed tetap utuh.
        partial = _as_text(e.stdout) + _as_text(e.stderr)
        subprocess.run(["docker", "restart", "-t", "1", container],
                       capture_output=True, timeout=120)
        note = (f"[command timed out after {timeout}s and was killed; "
                "the sandbox was restarted, so any background processes are "
                "gone — files on disk are intact. Give your script its own "
                "shorter internal timeouts so it always terminates.]")
        if partial and not partial.endswith("\n"):
            partial += "\n"
        return partial + note, 124


def docker_write_file(container: str, path: str, body: str) -> None:
    subprocess.run(
        ["docker", "exec", "-i", container, "bash", "-lc",
         f"mkdir -p $(dirname '{path}') && cat > '{path}'"],
        input=body, text=True, encoding="utf-8", check=True, timeout=60,
    )


def tail(s: str, n: int = 4000) -> str:
    return s if len(s) <= n else "[...dipotong...]\n" + s[-n:]


def observable_in_container(container: str, observable: str) -> bool:
    """Verifikasi mekanis klaim PASS_OBSERVABLE (lever r10): string harus
    benar-benar ada — di source repo (pesan framework) ATAU di script model
    sendiri (marker milik skenario). Grep -F: literal, tanpa regex."""
    docker_write_file(container, "/tmp/.pass_observable", observable + "\n")
    out, _ = docker_exec(
        container,
        "grep -rqF -f /tmp/.pass_observable /testbed && echo FOUND || echo MISSING",
        timeout=60)
    return "FOUND" in out


def emit_abort(em: Emitter, reason: str) -> None:
    """Tutup run yang crash sesuai kontrak §8: event abort + verdict
    wall="abort" + baris end di runs.jsonl."""
    em.event("reproduce", "abort", detail={"reason": reason})
    em.write_verdict(phases={}, wall="abort", pass_l1=None, pass_l2=None)
    em.run_end({"reproduce": "abort"}, "abort")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--rerun", type=int, required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--campaign", default="r-dev")
    ap.add_argument("--artifacts", default="../artifacts")
    ap.add_argument("--problem-file", default=None,
                    help="path file problem statement (teks)")
    ap.add_argument("--endpoint", default="http://10.8.0.86:8000/v1")
    ap.add_argument("--model", default="google/gemma-4-31B-it")
    ap.add_argument("--max-turns", type=int, default=40)
    args = ap.parse_args()

    problem = Path(args.problem_file).read_text(encoding="utf-8")
    contract = Path(__file__).with_name("reproduce_prompt.md").read_text(encoding="utf-8")

    em = Emitter(args.artifacts, args.campaign, args.case, args.rerun)
    console = em.run_dir / "console.log"

    def log(line: str) -> None:
        with open(console, "a", encoding="utf-8", newline="\n") as f:
            f.write(line.rstrip("\n") + "\n")

    container = f"gemma-work-{args.campaign}-{args.case}-r{args.rerun}"
    subprocess.run(["docker", "rm", "-f", container], capture_output=True)
    subprocess.run(["docker", "run", "-d", "--name", container, args.image,
                    "sleep", "infinity"], check=True, capture_output=True)
    log(f"[driver] work container {container} started ({args.image})")

    em.run_start()
    em.event("reproduce", "enter",
             budget={"msg_used": 0, "msg_limit": args.max_turns},
             detail={"model": args.model, "driver": "run_reproduce_gemma-v0"})

    system = contract + PROTOCOL_NOTE
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "PROBLEM STATEMENT:\n" + problem +
         "\n\nStart working now. The /testbed sandbox is at the base commit."},
    ]

    attempt = 1
    repro_md: str | None = None
    observed_fail = False
    self_check_prompted = False
    pass_observable: str | None = None
    done = False
    try:
        for turn in range(1, args.max_turns + 1):
            try:
                reply = chat(args.endpoint, args.model, messages)
            except Exception as e:  # transient endpoint error -> satu retry per turn
                log(f"[driver] chat error: {e}; retrying once")
                reply = chat(args.endpoint, args.model, messages)
            messages.append({"role": "assistant", "content": reply})
            log(f"[gemma t{turn}] {reply}")

            actions = parse_actions(reply)
            feedback_parts: list[str] = []
            for act in actions:
                if act.kind == "file":
                    docker_write_file(container, act.arg, act.body + "\n")
                    log(f"[driver] wrote {act.arg} ({len(act.body)} chars)")
                    feedback_parts.append(f"OK: file {act.arg} written.")
                elif act.kind == "bash":
                    out, code = docker_exec(container, act.body)
                    log(f"[exec] $ {act.body}\n{tail(out, 2000)}\n[exit {code}]")
                    feedback_parts.append(
                        f"OUTPUT (exit {code}):\n{tail(out)}")
                    if "repro.py" in act.body:
                        if "REPRO_STATUS: FAIL" in out:
                            observed_fail = True
                        else:
                            attempt += 1
                            em.event("reproduce", "retry", attempt=attempt,
                                     budget={"msg_used": turn, "msg_limit": args.max_turns},
                                     detail={"why": "run repro.py tanpa REPRO_STATUS: FAIL"})
                elif act.kind == "repro.md":
                    repro_md = act.body
                    log("[driver] repro.md candidate received")
                    feedback_parts.append("OK: repro.md received.")

            pass_observable = parse_pass_observable(reply) or pass_observable

            if has_done(reply):
                reason = done_rejection_reason(has_repro_md=repro_md is not None,
                                               observed_fail=observed_fail)
                if reason is not None:
                    log(f"[driver] DONE rejected: {reason}")
                    feedback_parts.append(reason)
                elif not self_check_prompted:
                    self_check_prompted = True
                    log("[driver] DONE deferred: self-check round injected")
                    feedback_parts.append(SELF_CHECK_MSG)
                elif (pass_observable is not None
                      and observable_in_container(container, pass_observable)):
                    done = True
                    log(f"[driver] DONE at turn {turn} (last attempt {attempt}); "
                        f"pass observable verified: {pass_observable!r}")
                    break
                else:
                    msg = observable_rejection(pass_observable)
                    if pass_observable is not None:
                        pass_observable = None  # klaim gagal; wajib deklarasi ulang
                    log(f"[driver] DONE rejected: {msg}")
                    feedback_parts.append(msg)

            if not actions and not feedback_parts:
                feedback_parts.append(
                    "No action block detected. Use ```bash / ```file:<path> / "
                    "```repro.md per the protocol, or close with DONE.")
            messages.append({"role": "user", "content": "\n\n".join(feedback_parts)})
    except Exception as e:
        log(f"[driver] crash: {e!r}")
        emit_abort(em, f"driver crash: {e!r}")
        subprocess.run(["docker", "stop", container], capture_output=True)
        print(json.dumps({"done": False, "aborted": True, "error": str(e)}))
        return 1

    # Salin artefak final
    files_dir = em.run_dir / "files"
    out, code = docker_exec(container, "cat /testbed/.pipe/repro.py")
    if code == 0:
        (files_dir / "repro.py").write_text(out, encoding="utf-8", newline="\n")
        log("[driver] files/repro.py copied from container")
    else:
        log("[driver] WARNING: /testbed/.pipe/repro.py missing in container")
    if repro_md is not None:
        (files_dir / "repro.md").write_text(
            compose_repro_md(repro_md, observed_fail=observed_fail),
            encoding="utf-8", newline="\n")
        log("[driver] files/repro.md written (mechanical slots filled by harness)")

    subprocess.run(["docker", "stop", container], capture_output=True)
    log(f"[driver] container {container} stopped (kept for debugging); "
        f"done={done}, turns={turn}, attempts={attempt}")
    print(json.dumps({"done": done, "turns": turn, "attempts": attempt,
                      "has_repro_md": repro_md is not None,
                      "has_repro_py": code == 0}))
    return 0


if __name__ == "__main__":
    main()
