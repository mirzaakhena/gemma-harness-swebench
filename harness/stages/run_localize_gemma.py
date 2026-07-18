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
                                           parse_actions)

PROTOCOL_NOTE = """
## How to work (action protocol — MANDATORY)

You work through action blocks in your replies. One reply may contain several
blocks; they are executed in order and I send the results back to you.

1. Run a shell command in the /testbed sandbox (read code, grep, run the
   repro/probe):
```bash
<command>
```
2. Write a small probe script — ONLY under /testbed/.pipe/ (writes anywhere
   else are REJECTED; the repository is read-only for you):
```file:/testbed/.pipe/probe.py
<file content>
```
3. Submit the final localize.md artifact (6 slots per the contract):
```localize.md
<localize.md content>
```
Once confident (you have explored and your evidence points at the mechanism
site), close with a single line containing exactly:
DONE

Work step by step: explore first, wait for my output, then take the next
step — do not pile every action into a single reply.
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
    log(f"[driver] container {container} start; input repro terpasang "
        f"dari {input_dir}")

    em.run_start()
    em.event("localize", "enter",
             budget={"msg_used": 0, "msg_limit": args.max_turns},
             detail={"model": args.model, "driver": "run_localize_gemma-v0",
                     "input_files": str(input_dir)})

    system = contract + PROTOCOL_NOTE
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content":
         "PROBLEM STATEMENT:\n" + problem +
         "\n\nREPRODUCE ARTIFACTS (frozen input, already gate-approved):\n" +
         repro_md +
         "\nThe repro script is installed at /testbed/.pipe/repro.py.\n\n"
         "Start working now. The /testbed sandbox is at the base commit."},
    ]

    attempt = 1
    localize_md: str | None = None
    ran_any_bash = False
    done = False
    for turn in range(1, args.max_turns + 1):
        try:
            reply = chat(args.endpoint, args.model, messages)
        except Exception as e:
            log(f"[driver] chat error: {e}; retry sekali")
            reply = chat(args.endpoint, args.model, messages)
        messages.append({"role": "assistant", "content": reply})
        log(f"[gemma t{turn}] {reply}")

        actions = parse_actions(reply)
        feedback_parts: list[str] = []
        for act in actions:
            if act.kind == "file":
                if not act.arg.startswith("/testbed/.pipe/"):
                    log(f"[driver] TOLAK tulis di luar .pipe: {act.arg}")
                    feedback_parts.append(
                        f"REJECTED: writing {act.arg} is not allowed — the "
                        "repository is read-only; probe scripts may only live "
                        "under /testbed/.pipe/.")
                    continue
                docker_write_file(container, act.arg, act.body + "\n")
                log(f"[driver] tulis {act.arg} ({len(act.body)} chars)")
                feedback_parts.append(f"OK: file {act.arg} written.")
            elif act.kind == "bash":
                ran_any_bash = True
                out, code = docker_exec(container, act.body)
                log(f"[exec] $ {act.body}\n{tail(out, 2000)}\n[exit {code}]")
                feedback_parts.append(f"OUTPUT (exit {code}):\n{tail(out)}")
            elif act.kind == "localize.md":
                localize_md = act.body
                log("[driver] kandidat localize.md diterima")
                feedback_parts.append("OK: localize.md received.")

        if has_done(reply):
            reason = done_rejection_localize(
                has_localize_md=localize_md is not None,
                ran_any_bash=ran_any_bash)
            if reason is not None:
                attempt += 1
                em.event("localize", "retry", attempt=attempt,
                         budget={"msg_used": turn, "msg_limit": args.max_turns},
                         detail={"why": "SELESAI ditolak"})
                log(f"[driver] SELESAI DITOLAK: {reason}")
                feedback_parts.append(reason)
            else:
                done = True
                log(f"[driver] SELESAI pada turn {turn}")
                break

        if not actions and not feedback_parts:
            feedback_parts.append(
                "No action block detected. Use ```bash / "
                "```file:/testbed/.pipe/... / ```localize.md, or close with "
                "DONE.")
        messages.append({"role": "user", "content": "\n\n".join(feedback_parts)})

    files_dir = em.run_dir / "files"
    if localize_md is not None:
        (files_dir / "localize.md").write_text(localize_md + "\n",
                                               encoding="utf-8", newline="\n")
        log("[driver] files/localize.md tertulis")
    (files_dir / "input-repro.md").write_text(repro_md, encoding="utf-8",
                                              newline="\n")

    subprocess.run(["docker", "stop", container], capture_output=True)
    log(f"[driver] container {container} di-stop; done={done}, turns={turn}")
    print(json.dumps({"done": done, "turns": turn,
                      "has_localize_md": localize_md is not None}))
    return 0


if __name__ == "__main__":
    main()
