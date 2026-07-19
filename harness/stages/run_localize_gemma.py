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
from harness.stages.localize_gates import (candidates_done_error,
                                           parse_candidates_md,
                                           parse_localize_md)

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
   from two different files):
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
    log(f"[driver] container {container} started; input repro installed "
        f"from {input_dir}")

    em.run_start()
    em.event("localize", "enter",
             budget={"msg_used": 0, "msg_limit": args.max_turns},
             detail={"model": args.model, "driver": "run_localize_gemma-v1",
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
        for cand in parse_candidates_md(candidates_md):
            target = cand["file"].lstrip("/")
            _, code = docker_exec(container, f"test -f '/testbed/{target}'")
            if code != 0:
                return (f"Not done yet: candidate file {cand['file']!r} does "
                        f"not exist in the repository — every candidate must "
                        f"be a real file.")
        return None
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
                candidates_error=candidates_error_now())
            if reason is not None:
                attempt += 1
                em.event("localize", "retry", attempt=attempt,
                         budget={"msg_used": turn, "msg_limit": args.max_turns},
                         detail={"why": "DONE rejected"})
                log(f"[driver] DONE rejected: {reason}")
                feedback_parts.append(reason)
            else:
                done = True
                log(f"[driver] DONE at turn {turn}")
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
        log("[driver] files/localize.md written")
    if candidates_md is not None:
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
