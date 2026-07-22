"""Driver stage FIX untuk Gemma (f-dev v0).

Spec: docs/superpowers/specs/2026-07-20-fix-stage-design.md.
Arsitektur: HARNESS mengiterasi kandidat dari candidates.md run L qualified
(urutan tulis, tanpa prioritas); satu attempt = satu kandidat = sesi Gemma
FRESH + container kerja BARU (pristine by construction). Bukti-dulu: DONE
ditolak sampai driver menyaksikan repro.py mencetak PASS (exact_status) di
container kerja; DONE diterima hanya bila pre-check dunia segar lolos
(evaluate_patch_in_fresh_world — fungsi yang SAMA dengan gate). Driver
TIDAK memvonis: exit + verdict.json ditulis run_fix_gates.

Pemakaian (dari root main):
    python harness/stages/run_fix_gemma.py --case django__django-11422
        --rerun 1 --image ghcr.io/...
        --input-localize-files <dir files run L qualified>
        --input-repro-files <dir files run R qualified>
        --problem-file cases/problems/django__django-11422.txt
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from harness.emit import Emitter
from harness.stages import chat_transport
# Pola R12 kini di util bersama (lever infra-abort): klasifikasi transport,
# konstanta, dan kelas error SATU untuk ketiga driver (R/L/F).
from harness.stages.chat_transport import (CHAT_BACKOFF_BASE_S, CHAT_RETRIES,
                                           CHAT_READ_TIMEOUT_S,
                                           ChatTransportError, chat,
                                           is_transport_error)
from harness.stages.fix_gates import compose_fix_md, fix_rejection_message
from harness.stages.fix_patch_runner import evaluate_patch_in_fresh_world
from harness.stages.fix_watchers import (DEGENERATE_P2_STREAK,
                                         DEGENERATE_REPLY_STREAK,
                                         ReplyHashWatcher, record_insist,
                                         shortlist_strays)
from harness.stages.gemma_protocol import (done_rejection_fix, exact_status,
                                           has_done, is_repro_run,
                                           no_action_feedback, parse_actions,
                                           retry_reason, token_format_note)
from harness.stages.localize_gates import parse_candidates_md

# --- R12: konstanta docker (transport/chat pindah ke chat_transport) --------
DOCKER_EXEC_TIMEOUT_S = 180  # guard exec perintah model di container kerja.
DOCKER_WRITE_TIMEOUT_S = 60  # guard tulis file ke container kerja.
DOCKER_CTL_TIMEOUT_S = 120   # guard kontrol docker (run/rm/stop).

# Bentuk aksi sah untuk pengingat no-action (R3): dikonsumsi no_action_feedback.
_ACTION_FORMS = (
    "```bash        -> run a shell command\n"
    "```file:<path> -> write that file with the block's content\n"
    "```fix.md      -> submit the fix.md artifact")

PROTOCOL_NOTE = """
## How to work (action protocol — MANDATORY)

You work through action blocks in your replies. One reply may contain several
blocks; they are executed in order and I send the results back to you.

1. Run a shell command in the /testbed sandbox (read code, edit files, run
   the repro):
```bash
<command>
```
2. Write/overwrite a file with the block's content:
```file:/testbed/path/to/file.py
<full file content>
```
3. Submit the final fix.md artifact (the lines listed in the contract):
```fix.md
<fix.md content>
```
Close with a single line containing exactly:
DONE
Declare DONE only after you have run the repro, seen REPRO_STATUS: PASS in
its output, and submitted the fix.md block.

Work step by step: act, wait for my output, then take the next step based on
what you observed. Keep prose minimal; focus on the next action.
"""


@dataclass(frozen=True)
class FixInputs:
    candidates: list[dict]
    repro_md: str
    repro_py: str


def load_fix_inputs(localize_dir: Path, repro_dir: Path) -> FixInputs:
    """Input beku (spec §9): candidates.md dari run L qualified terakhir,
    repro.md + repro.py dari run R qualified terakhir."""
    candidates = parse_candidates_md(
        (localize_dir / "candidates.md").read_text(encoding="utf-8"))
    return FixInputs(
        candidates=candidates,
        repro_md=(repro_dir / "repro.md").read_text(encoding="utf-8"),
        repro_py=(repro_dir / "repro.py").read_text(encoding="utf-8"))


def compose_fix_seed(problem: str, repro_md: str, repro_py: str,
                     candidate: dict) -> str:
    """Seed per attempt (spec §3, English): problem + repro.md verbatim +
    ISI repro.py (P21: model melihat lembar ujiannya) + kandidat AKTIF
    saja (scope positif; kandidat lain tidak pernah disebut)."""
    return ("PROBLEM STATEMENT:\n" + problem
            + "\n\nREPRODUCE ARTIFACTS (frozen input, already "
              "gate-approved):\n" + repro_md
            + "\nThe frozen repro script is installed at "
              "/testbed/.pipe/repro.py; this is its content:\n"
            + "```python\n" + repro_py + "\n```\n"
            + "\nYOUR EDIT SITE:\n"
            + f"file: {candidate['file']}\n"
            + f"evidence: {candidate['evidence']}\n"
            + f"expectation: {candidate['expectation']}\n"
            + "\nStart working now. The /testbed sandbox is at the base "
              "commit; the bug is present.")


def chat_with_retry(endpoint: str, model: str, messages: list[dict],
                    retries: int = CHAT_RETRIES,
                    backoff_base: int = CHAT_BACKOFF_BASE_S,
                    log=None, sleep=time.sleep) -> str:
    """R12 (kini util bersama chat_transport): wrapper tipis — chat_fn
    me-resolve `chat` MODUL INI saat dipanggil, jadi monkeypatch test pada
    drv.chat tetap bekerja; perilaku identik dgn versi lama."""
    return chat_transport.chat_with_retry(
        endpoint, model, messages, retries=retries,
        backoff_base=backoff_base, log=log, sleep=sleep,
        chat_fn=lambda e, m, ms: chat(e, m, ms))


def docker_exec(container: str, cmd: str,
                timeout: int = DOCKER_EXEC_TIMEOUT_S) -> tuple[str, int]:
    p = subprocess.run(
        ["docker", "exec", container, "bash", "-lc", cmd],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    return (p.stdout or "") + (p.stderr or ""), p.returncode


def docker_ctl(cmd: list[str], check: bool = False):
    """R12: perintah kontrol docker (rm/run/stop) ber-guard timeout —
    daemon macet tak boleh menggantung driver. check=False = best-effort:
    timeout ditelan (kegagalan cleanup bukan kegagalan run)."""
    try:
        return subprocess.run(cmd, check=check, capture_output=True,
                              timeout=DOCKER_CTL_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        if check:
            raise
        return None


def docker_write_file(container: str, path: str, body: str) -> None:
    # Bytes mentah, BUKAN text=True (pelajaran r15: mode teks Windows
    # menulis \r\n ke pipe; kontrak §2: byte \r adalah BUG).
    data = body.replace("\r\n", "\n").encode("utf-8")
    subprocess.run(
        ["docker", "exec", "-i", container, "bash", "-lc",
         f"mkdir -p $(dirname '{path}') && cat > '{path}'"],
        input=data, check=True, timeout=DOCKER_WRITE_TIMEOUT_S,
    )


def ship_repro_to_container(container: str, repro_dir: Path) -> list[str]:
    """Tulis repro beku ke dunia kerja — TERMASUK `pipe_runtime.py` bila ada
    (LV-09): repro qualified yang ber-`from pipe_runtime import App` sebelumnya
    mati ImportError di container kerja FIX (dunia segar gate sudah benar via
    repro_sandbox_runner; dunia kerja bolong — 588 kejadian di 11910 r1).
    Kembalikan daftar nama file yang dikirim (untuk log/test)."""
    docker_write_file(container, "/testbed/.pipe/repro.py",
                      (repro_dir / "repro.py").read_text(encoding="utf-8"))
    shipped = ["repro.py"]
    rt = repro_dir / "pipe_runtime.py"
    if rt.is_file():
        docker_write_file(container, "/testbed/.pipe/pipe_runtime.py",
                          rt.read_text(encoding="utf-8"))
        shipped.append("pipe_runtime.py")
    return shipped


def tail(s: str, n: int = 4000) -> str:
    return s if len(s) <= n else "[...dipotong...]\n" + s[-n:]


def _ensure_nl(s: str) -> str:
    return s if not s or s.endswith("\n") else s + "\n"


DIFF_CMD = ("cd /testbed && git add -N -- . ':(exclude).pipe' "
            ">/dev/null 2>&1; git diff 2>/dev/null")


def collect_work_diff(container: str) -> str:
    """Diff container kerja: `git add -N` (file baru ter-cover, kontrak
    §10) dengan .pipe dikecualikan (workspace probe bukan bagian fix),
    lalu `git diff`. Gagal baca -> "" (diff kosong ditolak evaluator)."""
    out, code = docker_exec(container, DIFF_CMD, timeout=120)
    return out if code == 0 else ""


def emit_abort(em: Emitter, reason: str) -> None:
    """Tutup run crash sesuai kontrak §8."""
    em.event("fix", "abort", detail={"reason": reason})
    em.write_verdict(phases={}, wall="abort", pass_l1=None, pass_l2=None)
    em.run_end({"fix": "abort"}, "abort")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--rerun", type=int, required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--input-localize-files", required=True,
                    help="dir files/ run LOCALIZE qualified "
                         "(berisi candidates.md)")
    ap.add_argument("--input-repro-files", required=True,
                    help="dir files/ run REPRODUCE qualified "
                         "(repro.md + repro.py beku)")
    ap.add_argument("--problem-file", required=True)
    ap.add_argument("--campaign", default="f-dev")
    ap.add_argument("--artifacts", default="../artifacts")
    ap.add_argument("--endpoint", default="http://10.8.0.86:8000/v1")
    ap.add_argument("--model", default="google/gemma-4-31B-it")
    ap.add_argument("--max-turns", type=int, default=40)
    args = ap.parse_args()

    problem = Path(args.problem_file).read_text(encoding="utf-8")
    localize_dir = Path(args.input_localize_files)
    repro_dir = Path(args.input_repro_files)
    inputs = load_fix_inputs(localize_dir, repro_dir)
    contract = Path(__file__).with_name("fix_prompt.md").read_text(
        encoding="utf-8")

    em = Emitter(args.artifacts, args.campaign, args.case, args.rerun)
    console = em.run_dir / "console.log"

    def log(line: str) -> None:
        with open(console, "a", encoding="utf-8", newline="\n") as f:
            f.write(line.rstrip("\n") + "\n")

    files_dir = em.run_dir / "files"
    attempts_dir = files_dir / "attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)
    (files_dir / "input-candidates.md").write_text(
        (localize_dir / "candidates.md").read_text(encoding="utf-8"),
        encoding="utf-8", newline="\n")
    (files_dir / "input-repro.md").write_text(
        inputs.repro_md, encoding="utf-8", newline="\n")

    em.run_start()
    em.event("fix", "enter",
             budget={"msg_used": 0, "msg_limit": args.max_turns},
             detail={"model": args.model, "driver": "run_fix_gemma-v0",
                     "input_localize": str(localize_dir),
                     "input_repro": str(repro_dir),
                     "candidates": [c["file"] for c in inputs.candidates]})

    winner: int | None = None
    winner_file: str | None = None
    attempts_meta: list[dict] = []
    container = ""
    # N4: rotasi kandidat lewat ANTRIAN indeks 0-based (urutan default =
    # urutan tulis shortlist, persis perilaku lama); relaksasi attempt-lock
    # bisa MEMPROMOSIKAN kandidat spesifik ke depan antrian. Tiap kandidat
    # tetap di-attempt maksimal SEKALI.
    pending = list(range(len(inputs.candidates)))
    total = len(inputs.candidates)
    k = 0
    try:
        while pending:
            ci = pending.pop(0)
            cand = inputs.candidates[ci]
            k += 1
            # Attempt ke-k = kandidat peringkat ci+1: container kerja BARU +
            # sesi FRESH (spec §2 — pristine by construction).
            container = (f"gemma-work-{args.campaign}-{args.case}"
                         f"-r{args.rerun}-a{k}")
            docker_ctl(["docker", "rm", "-f", container])
            docker_ctl(["docker", "run", "-d", "--name", container,
                        args.image, "sleep", "infinity"], check=True)
            shipped = ship_repro_to_container(container, repro_dir)
            log(f"[driver] attempt {k}/{total}: container "
                f"{container} started; candidate {cand['file']}; "
                f"repro inputs shipped: {', '.join(shipped)}")

            messages = [
                {"role": "system", "content": contract + PROTOCOL_NOTE},
                {"role": "user", "content": compose_fix_seed(
                    problem, inputs.repro_md, inputs.repro_py, cand)},
            ]
            observed_pass = False
            fix_md: str | None = None
            turn = 0
            hash_watcher = ReplyHashWatcher()   # N1: satu watcher per attempt
            insist_counts: dict[int, int] = {}  # N4: penolakan per peringkat
            for turn in range(1, args.max_turns + 1):
                reply = chat_with_retry(args.endpoint, args.model, messages,
                                        log=log)
                messages.append({"role": "assistant", "content": reply})
                log(f"[gemma a{k} t{turn}] {reply}")

                # N1: loop degenerat temp-0 — 3 reply md5-identik beruntun,
                # ATAU (N1b) siklus periode-2 A-B-A-B (3 hit jarak-2).
                # TANPA injeksi konten: akhiri attempt dini, biarkan rotasi
                # kandidat mengambil alih (mekanisme penyelamat 12184 r9).
                # Label event mengikuti pola yang menembak (watcher.trigger).
                if hash_watcher.observe(reply):
                    limit = (DEGENERATE_REPLY_STREAK
                             if hash_watcher.trigger == "reply-hash"
                             else DEGENERATE_P2_STREAK)
                    em.event("fix", "retry", attempt=k,
                             budget={"msg_used": turn,
                                     "msg_limit": args.max_turns},
                             detail={"why": ("attempt-ended: degenerate-loop "
                                             f"{hash_watcher.trigger} "
                                             f"x{limit}"),
                                     "reply_md5": hash_watcher.last_md5,
                                     "turns_saved": args.max_turns - turn})
                    log(f"[driver] attempt {k} ended early at turn {turn}: "
                        f"degenerate loop {hash_watcher.trigger} x{limit} "
                        f"(md5 {hash_watcher.last_md5}); "
                        f"{args.max_turns - turn} turns saved")
                    break

                actions = parse_actions(reply)
                feedback_parts: list[str] = []
                for act in actions:
                    if act.kind == "file":
                        docker_write_file(container, act.arg, act.body + "\n")
                        log(f"[driver] wrote {act.arg} "
                            f"({len(act.body)} chars)")
                        feedback_parts.append(f"OK: file {act.arg} written.")
                    elif act.kind == "bash":
                        out, code = docker_exec(container, act.body)
                        log(f"[exec] $ {act.body}\n{tail(out, 2000)}\n"
                            f"[exit {code}]")
                        feedback_parts.append(
                            f"OUTPUT (exit {code}):\n{tail(out)}")
                        if is_repro_run(act.body):
                            # Bukti-dulu: PASS tersaksikan = exact_status
                            # (standar token TUNGGAL baris-eksak, pola R).
                            if exact_status(out) == "PASS":
                                observed_pass = True
                            else:
                                em.event("fix", "retry", attempt=k,
                                         budget={"msg_used": turn,
                                                 "msg_limit": args.max_turns},
                                         detail={"why": retry_reason(
                                             out, code, expected="PASS")})
                                note = token_format_note(out)
                                if note is not None:
                                    feedback_parts.append(note)
                    elif act.kind == "fix.md":
                        fix_md = act.body
                        log("[driver] fix.md candidate received")
                        feedback_parts.append("OK: fix.md received.")

                if has_done(reply):
                    reason = done_rejection_fix(
                        has_fix_md=fix_md is not None,
                        observed_pass=observed_pass)
                    if reason is not None:
                        em.event("fix", "retry", attempt=k,
                                 budget={"msg_used": turn,
                                         "msg_limit": args.max_turns},
                                 detail={"why": f"done-rejected: {reason}",
                                         "has_fix_md": fix_md is not None,
                                         "observed_pass": observed_pass})
                        log(f"[driver] DONE rejected: {reason}")
                        feedback_parts.append(reason)
                    else:
                        # Pre-check DONE: vonis dunia segar dengan evaluator
                        # yang SAMA dengan gate (standar tunggal, spec §4).
                        diff_text = collect_work_diff(container)
                        result = evaluate_patch_in_fresh_world(
                            args.image, diff_text, cand["file"],
                            args.input_repro_files)
                        if result.ok:
                            winner = k
                            winner_file = cand["file"]
                            (files_dir / "fix.diff").write_text(
                                _ensure_nl(diff_text),
                                encoding="utf-8", newline="\n")
                            (attempts_dir / f"attempt-{k}.diff").write_text(
                                _ensure_nl(diff_text),
                                encoding="utf-8", newline="\n")
                            # Slot CANDIDATE = peringkat kandidat di
                            # shortlist (ci+1) — identik dgn nomor attempt
                            # kecuali N4 mengubah urutan rotasi.
                            (files_dir / "fix.md").write_text(
                                compose_fix_md(
                                    fix_md, cand["file"], ci + 1,
                                    "PASS,PASS (frozen repro, fresh "
                                    "container pair)"),
                                encoding="utf-8", newline="\n")
                            log(f"[driver] DONE accepted at attempt {k} "
                                f"turn {turn}: fresh pair PASS,PASS")
                            break
                        em.event("fix", "retry", attempt=k,
                                 budget={"msg_used": turn,
                                         "msg_limit": args.max_turns},
                                 detail={"why": ("done-rejected: pre-check "
                                                 f"{result.reason}"),
                                         "touched": list(result.touched),
                                         "pair": {
                                             "status1": result.status1,
                                             "status2": result.status2,
                                             "exit1": result.exit1,
                                             "exit2": result.exit2,
                                             "run1_tail":
                                                 result.run1_tail[:200],
                                             "run2_tail":
                                                 result.run2_tail[:200]}})
                        log("[driver] DONE rejected: pre-check "
                            f"{result.reason}")
                        # N4: relaksasi attempt-lock — model berkeras
                        # menyentuh kandidat SAH shortlist peringkat lain.
                        # >= ambang -> akhiri attempt dini + promosikan
                        # kandidat itu ke depan antrian (bila belum pernah
                        # di-attempt; kalau sudah, keterbatasan rotasi:
                        # cukup akhiri dini, tercatat promoted=False).
                        # File di LUAR shortlist tetap ditolak spt biasa.
                        if result.reason == "off-candidate-files":
                            hit = record_insist(
                                insist_counts,
                                shortlist_strays(
                                    result.touched,
                                    [c["file"] for c in inputs.candidates],
                                    cand["file"]))
                            if hit is not None:
                                target = hit - 1
                                promoted = target in pending
                                if promoted:
                                    pending.remove(target)
                                    pending.insert(0, target)
                                em.event(
                                    "fix", "retry", attempt=k,
                                    budget={"msg_used": turn,
                                            "msg_limit": args.max_turns},
                                    detail={
                                        "why": ("attempt-ended: model-"
                                                f"insists-candidate-{hit}"),
                                        "insisted_file":
                                            inputs.candidates[target]["file"],
                                        "rejections": insist_counts[hit],
                                        "promoted": promoted})
                                log(f"[driver] attempt {k} ended early at "
                                    f"turn {turn}: model insisted on "
                                    f"shortlist candidate {hit} "
                                    f"({inputs.candidates[target]['file']}) "
                                    f"{insist_counts[hit]}x; "
                                    f"promoted={promoted}")
                                break
                        feedback_parts.append(
                            fix_rejection_message(result, cand["file"]))

                if not actions and not feedback_parts:
                    feedback_parts.append(
                        no_action_feedback(reply, _ACTION_FORMS))
                messages.append({"role": "user",
                                 "content": "\n\n".join(feedback_parts)})

            if winner is None:
                # Telemetri kandidat gagal: diff terakhir attempt (autopsi).
                (attempts_dir / f"attempt-{k}.diff").write_text(
                    _ensure_nl(collect_work_diff(container)),
                    encoding="utf-8", newline="\n")
            attempts_meta.append(
                {"attempt": k, "candidate_file": cand["file"],
                 "turns": turn,
                 "result": "win" if winner == k else "exhausted"})
            docker_ctl(["docker", "stop", container])
            log(f"[driver] attempt {k} finished: "
                f"{'win' if winner == k else 'exhausted'} "
                f"after {turn} turns")
            if winner is not None:
                break
            em.event("fix", "retry", attempt=k,
                     budget={"msg_used": turn, "msg_limit": args.max_turns},
                     detail={"why": (f"candidate {k} exhausted without an "
                                     "accepted DONE"),
                             "candidate_file": cand["file"]})
    except ChatTransportError as e:
        # R12: kegagalan transport final = kelas INFRA, bukan model —
        # gagal CEPAT dan jujur, jangan menggantung (12184 r11, 15388 r9).
        log(f"[driver] INFRA failure (model endpoint transport): {e}")
        emit_abort(em, f"infra transport failure: {e}")
        if container:
            docker_ctl(["docker", "stop", container])
        print(json.dumps({"winner_attempt": None, "aborted": True,
                          "error": f"infra-transport: {e}"}))
        return 1
    except Exception as e:
        import traceback
        log(f"[driver] crash: {e!r}\n{traceback.format_exc()}")
        emit_abort(em, f"driver crash: {e!r}")
        if container:
            docker_ctl(["docker", "stop", container])
        print(json.dumps({"winner_attempt": None, "aborted": True,
                          "error": str(e)}))
        return 1

    fix_run = {"winner_attempt": winner,
               "candidate_file": winner_file,
               "candidates": [c["file"] for c in inputs.candidates],
               "attempts": attempts_meta}
    (files_dir / "fix_run.json").write_text(
        json.dumps(fix_run, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    log(f"[driver] run finished: winner_attempt={winner}; "
        "verdict is written by the gate step")
    print(json.dumps(fix_run, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    main()
