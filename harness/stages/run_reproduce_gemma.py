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
                                           parse_actions)
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
3. Submit the final repro.md artifact — interpretive slots only (SYMPTOM,
   TRIGGER, EXPECTED vs ACTUAL); the harness appends REPRO COMMAND and
   CONFIRMED-AT-BASE itself:
```repro.md
<repro.md content>
```
Once ALL final outputs are ready (you have run repro.py and seen
REPRO_STATUS: FAIL, and you have submitted the repro.md block), close with a
single line containing exactly:
DONE

EVIDENCE RULE: DONE is only accepted if, in this session, I (the driver) have
witnessed your repro.py execution print REPRO_STATUS: FAIL. Writing
CONFIRMED-AT-BASE: yes without ever seeing FAIL is a contract violation.
Work step by step: explore first, wait for my output, then take the next
step — do not pile every action into a single reply.

Do not write prose beyond what is needed; focus on the next action.
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
    subprocess.run(
        ["docker", "exec", "-i", container, "bash", "-lc",
         f"mkdir -p $(dirname '{path}') && cat > '{path}'"],
        input=body, text=True, encoding="utf-8", check=True, timeout=60,
    )


def tail(s: str, n: int = 4000) -> str:
    return s if len(s) <= n else "[...dipotong...]\n" + s[-n:]


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
    done = False
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

        if has_done(reply):
            reason = done_rejection_reason(has_repro_md=repro_md is not None,
                                           observed_fail=observed_fail)
            if reason is not None:
                log(f"[driver] DONE rejected: {reason}")
                feedback_parts.append(reason)
            else:
                done = True
                log(f"[driver] DONE at turn {turn} (last attempt {attempt})")
                break

        if not actions and not feedback_parts:
            feedback_parts.append(
                "No action block detected. Use ```bash / ```file:<path> / "
                "```repro.md per the protocol, or close with DONE.")
        messages.append({"role": "user", "content": "\n\n".join(feedback_parts)})

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
