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

import tempfile

from harness.emit import Emitter
from harness.stages import rule_catalog
from harness.stages.gemma_protocol import (done_rejection_reason,
                                           format_reminder,
                                           fresh_pair_rejection, has_done,
                                           has_fences, is_repro_run,
                                           literal_emitted_by_script,
                                           next_step_nudge,
                                           observable_candidates,
                                           observable_rejection,
                                           parse_actions,
                                           parse_pass_observable,
                                           parse_review,
                                           repeated_error_note,
                                           retry_reason, review_feedback)
from harness.stages.repro_sandbox_runner import run_once
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
   PASS_OBSERVABLE: <the string your script matches on, copied exactly as
   written in the repository source — keep placeholders like %s if present>
2. Show that your script exercises the same scenario the issue describes:
   name the entry point / command the user runs in the issue, and point to
   the line in YOUR script that runs that same path. If your script builds
   the state by hand instead, revise it to run the real path.
3. When your PASS observable is an event a background mechanism must
   notice (a reload, a watcher, a poller): name the line in YOUR script
   that implements the contract's positive control — the same detection
   machinery catching the event through a path that already works at the
   base commit — and the line that lets the mechanism settle its baseline
   (one full sampling interval after it reports ready) before any trigger
   fires. If either line is missing, revise the script first. If no
   background mechanism is involved, answer: not applicable.

If all answers hold, declare DONE again. Otherwise revise your script,
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
    # Bytes mentah, BUKAN text=True: mode teks Windows menerjemahkan \n ->
    # \r\n saat menulis ke pipe (bug nyata r15 — pattern grep berakhiran \r
    # tak pernah match source LF; kontrak §2: byte \r di file adalah BUG).
    data = body.replace("\r\n", "\n").encode("utf-8")
    subprocess.run(
        ["docker", "exec", "-i", container, "bash", "-lc",
         f"mkdir -p $(dirname '{path}') && cat > '{path}'"],
        input=data, check=True, timeout=60,
    )


def tail(s: str, n: int = 4000) -> str:
    return s if len(s) <= n else "[...dipotong...]\n" + s[-n:]


def observable_in_container(container: str, observable: str) -> bool:
    """Verifikasi mekanis klaim PASS_OBSERVABLE (lever r10): string harus
    benar-benar ada — di source repo (pesan framework) ATAU di script model
    sendiri (marker milik skenario). Grep -F: literal, tanpa regex."""
    candidates = observable_candidates(observable)
    docker_write_file(container, "/tmp/.pass_observable",
                      "\n".join(candidates) + "\n")
    # Sumber repo SAJA (r26: --exclude-dir=.pipe menutup lubang self-match —
    # literal pencarian di script sendiri bukan bukti string itu nyata).
    out, _ = docker_exec(
        container,
        "grep -rqF -f /tmp/.pass_observable --exclude-dir=.pipe /testbed "
        "&& echo FOUND || echo MISSING",
        timeout=60)
    if "FOUND" in out:
        return True
    script, code = docker_exec(container, "cat /testbed/.pipe/repro.py")
    return code == 0 and literal_emitted_by_script(script, observable)


JUDGE_SYSTEM = """You review a bug-reproduction script against its contract.
Close your reply with exactly one line:
REVIEW: OK
or
REVIEW: ISSUES
followed, for ISSUES, by a short numbered list naming the specific contract
rule violated and the concrete change needed. Judge ONLY against the contract
below — add no requirements of your own. Pay particular attention to whether
the PASS observable can actually be produced once the bug is fixed, and to
timing around background mechanisms.

## Contract
"""


def judge_review(endpoint: str, model: str, contract: str, problem: str,
                 script: str, repro_md_text: str | None,
                 ) -> tuple[bool, str | None, str]:
    """Reviewer fresh-context (usulan Mirza): satu percakapan bersih menilai
    script vs kontrak. Advisory — vonis tetap milik gate mekanis.
    Return (ok, issues, raw_reply)."""
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM + contract},
        {"role": "user", "content":
            "PROBLEM STATEMENT:\n" + problem +
            "\n\n## Script (/testbed/.pipe/repro.py)\n```python\n" + script +
            "\n```\n\n## repro.md (interpretive part)\n" +
            (repro_md_text or "(not submitted)") +
            "\n\nReview now."},
    ]
    reply = chat(endpoint, model, messages)
    ok, issues = parse_review(reply)
    return ok, issues, reply


def fresh_sandbox_output(container: str, image: str,
                         timeout: int = 300) -> tuple[str, int]:
    """Salin repro.py dari work container, jalankan sekali di container
    segar (tanpa patch); kembalikan (output, exit)."""
    body, code = docker_exec(container, "cat /testbed/.pipe/repro.py")
    if code != 0:
        return ("[pre-check] /testbed/.pipe/repro.py missing in work "
                "container", 2)
    tmpdir = tempfile.mkdtemp(prefix="fresh-check-")
    repro = Path(tmpdir) / "repro.py"
    repro.write_text(body, encoding="utf-8", newline="\n")
    result = run_once(image, tmpdir, timeout)
    return result["output"], result["exit"]


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
    contract = rule_catalog.core_contract()

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
    last_retry_why: str | None = None
    judge_prompted = False
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
                    if is_repro_run(act.body):
                        # Vonis repro SELALU dari dunia segar (keputusan
                        # Mirza 2026-07-19): feedback mid-loop = kebenaran
                        # yang sama dengan gate, state bengkel tak menipu.
                        out, code = fresh_sandbox_output(container, args.image)
                        label = f"OUTPUT (fresh sandbox, exit {code})"
                        log(f"[exec-fresh] $ {act.body}\n{tail(out, 2000)}\n[exit {code}]")
                        feedback_parts.append(f"{label}:\n{tail(out)}")
                        if "REPRO_STATUS: FAIL" in out:
                            if not observed_fail:
                                # Checkpoint known-good (paket hardening,
                                # disetujui Mirza): versi script saat FAIL
                                # pertama disaksikan diamankan — tulisan
                                # ulang yang lebih rusak tak menghapusnya.
                                body, c2 = docker_exec(
                                    container, "cat /testbed/.pipe/repro.py")
                                if c2 == 0:
                                    (em.run_dir / "files" /
                                     "repro-first-fail.py").write_text(
                                        body, encoding="utf-8", newline="\n")
                                    log("[driver] checkpoint saved: "
                                        "files/repro-first-fail.py")
                            observed_fail = True
                        else:
                            attempt += 1
                            why = retry_reason(out, code)
                            em.event("reproduce", "retry", attempt=attempt,
                                     budget={"msg_used": turn, "msg_limit": args.max_turns},
                                     detail={"why": why})
                            note = repeated_error_note(last_retry_why, why)
                            if note is not None:
                                log("[driver] repeated-error note injected")
                                feedback_parts.append(note)
                            last_retry_why = why
                            if code != 0 and "REPRO_STATUS" not in out:
                                feedback_parts.append(
                                    rule_catalog.inject("crash-repair"))
                    else:
                        out, code = docker_exec(container, act.body)
                        log(f"[exec] $ {act.body}\n{tail(out, 2000)}\n[exit {code}]")
                        feedback_parts.append(
                            f"OUTPUT (exit {code}):\n{tail(out)}")
                elif act.kind == "repro.md":
                    repro_md = act.body
                    log("[driver] repro.md candidate received")
                    feedback_parts.append("OK: repro.md received.")

            pass_observable = parse_pass_observable(reply) or pass_observable

            if has_done(reply):
                def reject_event(why: str) -> None:
                    em.event("reproduce", "retry", attempt=attempt,
                             budget={"msg_used": turn, "msg_limit": args.max_turns},
                             detail={"why": why})

                reason = done_rejection_reason(has_repro_md=repro_md is not None,
                                               observed_fail=observed_fail)
                if reason is not None:
                    why = ("done-rejected: repro.md not submitted"
                           if repro_md is None
                           else "done-rejected: REPRO_STATUS: FAIL not observed yet")
                    reject_event(why)
                    log(f"[driver] DONE rejected: {reason}")
                    feedback_parts.append(reason)
                elif not self_check_prompted:
                    self_check_prompted = True
                    log("[driver] DONE deferred: self-check round injected")
                    feedback_parts.append(SELF_CHECK_MSG)
                elif (pass_observable is not None
                      and observable_in_container(container, pass_observable)):
                    fresh_out1, _ = fresh_sandbox_output(container, args.image)
                    fresh_out2, _ = fresh_sandbox_output(container, args.image)
                    fresh_reject = fresh_pair_rejection(fresh_out1, fresh_out2)
                    if fresh_reject is None:
                        review_blocked = False
                        if not judge_prompted:
                            judge_prompted = True
                            script_text, sc = docker_exec(
                                container, "cat /testbed/.pipe/repro.py")
                            ok, issues, raw = judge_review(
                                args.endpoint, args.model, contract, problem,
                                script_text if sc == 0 else "(missing)",
                                repro_md)
                            log(f"[judge] {raw}")
                            if not ok:
                                reject_event("done-deferred: independent "
                                             "review found issues")
                                log("[driver] DONE deferred: judge review "
                                    "found issues")
                                feedback_parts.append(review_feedback(issues))
                                review_blocked = True
                        if not review_blocked:
                            done = True
                            log(f"[driver] DONE at turn {turn} "
                                f"(last attempt {attempt}); pass observable "
                                f"verified: {pass_observable!r}; "
                                "fresh-sandbox pre-check OK (2 runs)")
                            break
                    else:
                        reject_event("done-rejected: fresh-sandbox pair "
                                     "without consistent REPRO_STATUS: FAIL")
                        log("[driver] DONE rejected: fresh-sandbox "
                            "pre-check failed")
                        feedback_parts.append(fresh_reject)
                else:
                    reject_event("done-rejected: PASS_OBSERVABLE "
                                 + ("not declared" if pass_observable is None
                                    else f"not found in source or script: {pass_observable!r}"))
                    msg = observable_rejection(pass_observable)
                    if pass_observable is not None:
                        pass_observable = None  # klaim gagal; wajib deklarasi ulang
                    log(f"[driver] DONE rejected: {msg}")
                    feedback_parts.append(msg)
                    feedback_parts.append(rule_catalog.inject("source-pass-side"))

            if not has_done(reply):
                nudge = next_step_nudge(observed_fail=observed_fail,
                                        has_repro_md=repro_md is not None)
                if nudge is not None:
                    feedback_parts.append(nudge)
                    feedback_parts.append(rule_catalog.inject("early-draft"))

            if not actions and not feedback_parts:
                if has_fences(reply):
                    log("[driver] fenced block(s) present but none parsed as "
                        "action; format reminder sent")
                    feedback_parts.append(format_reminder())
                else:
                    feedback_parts.append(
                        "No action block detected. Use ```bash / ```file:<path> / "
                        "```repro.md per the protocol, or close with DONE.")
            messages.append({"role": "user", "content": "\n\n".join(feedback_parts)})
    except Exception as e:
        import traceback
        log(f"[driver] crash: {e!r}\n{traceback.format_exc()}")
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
