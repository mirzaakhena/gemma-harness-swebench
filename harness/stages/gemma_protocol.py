"""Parser protokol teks untuk driver Gemma.

Aksi = fenced block dengan info-string khusus:
  ```bash            -> jalankan command di sandbox
  ```file:<path>     -> tulis file di sandbox
  ```repro.md        -> artefak final repro.md
Fenced block dengan bahasa lain (python, dsb.) BUKAN aksi.
Penanda selesai: baris `DONE` di LUAR fenced block.

Seluruh teks yang dilihat model (penanda + pesan penolakan) berbahasa Inggris
(keputusan Mirza 2026-07-18); komentar/docstring internal tetap Indonesia.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_FENCE_RE = re.compile(
    r"^```([^\r\n]*)\r?\n(.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True)
class Action:
    kind: str          # bash | file | repro.md
    arg: str | None    # path untuk kind=file
    body: str


def _normalize(body: str) -> str:
    return body.replace("\r\n", "\n").rstrip("\n")


def parse_actions(text: str) -> list[Action]:
    actions = []
    for m in _FENCE_RE.finditer(text):
        info = m.group(1).strip()
        body = _normalize(m.group(2))
        if info == "bash":
            actions.append(Action(kind="bash", arg=None, body=body))
        elif info.startswith("file:"):
            actions.append(Action(kind="file", arg=info[len("file:"):].strip(),
                                  body=body))
        elif info in ("repro.md", "localize.md"):
            actions.append(Action(kind=info, arg=None, body=body))
    return actions


def has_done(text: str) -> bool:
    outside = _FENCE_RE.sub("", text)
    return any(line.strip() == "DONE" for line in outside.splitlines())


def done_rejection_reason(has_repro_md: bool, observed_fail: bool) -> str | None:
    """Aturan bukti-dulu-baru-SELESAI. None = SELESAI diterima.

    Lahir dari kegagalan run r2 (11422): model menyerahkan CONFIRMED-AT-BASE
    yes + SELESAI padahal eksekusi repro-nya crash — konfirmasi tanpa bukti.
    """
    if not has_repro_md:
        return ("Not done yet: submit the ```repro.md block first, then "
                "declare DONE.")
    if not observed_fail:
        return ("Not done yet: run `python /testbed/.pipe/repro.py` and get "
                "`REPRO_STATUS: FAIL` in its output first, then declare DONE.")
    return None


def parse_pass_observable(text: str) -> str | None:
    """Deklarasi `PASS_OBSERVABLE: <literal>` di luar fenced block.

    Lahir dari r9 (11422): model MENGARANG kutipan source di self-check
    ("Detected change" + nomor baris fiktif) dan driver menerimanya tanpa
    verifikasi. Deklarasi ini yang diverifikasi mekanis oleh driver.
    """
    outside = _FENCE_RE.sub("", text)
    for line in outside.splitlines():
        s = line.strip()
        if s.startswith("PASS_OBSERVABLE:"):
            val = s[len("PASS_OBSERVABLE:"):].strip()
            # Model lazim membungkus string dengan kutip (kasus nyata r12:
            # 'changed, reloading.'; r5 11797: backtick markdown) — kutip
            # berpasangan bukan bagian observable, buang satu lapis.
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"', "`"):
                val = val[1:-1]
            if val:
                return val
    return None


def observable_candidates(observable: str) -> list[str]:
    """Kandidat string untuk verifikasi grep — full string dulu, lalu trim
    hingga 2 kata dari depan/belakang (min 2 kata tersisa).

    Lahir dari r14: model mendeklarasikan bentuk RUNTIME
    ("Watching for file changes with StatReloader") sementara source
    menyimpan template %s — deklarasi jujur tertolak. Trim kecil menoleransi
    segmen hasil interpolasi di tepi string; karangan utuh tetap tertolak
    karena butuh >=2 kata berurutan yang benar-benar ada."""
    words = observable.split()
    out: list[str] = []
    for front in range(0, 3):
        for back in range(0, 3):
            if len(words) - front - back < 2:
                continue
            cand = " ".join(words[front:len(words) - back if back else None])
            if cand and cand not in out:
                out.append(cand)
    if observable and observable not in out:
        out.insert(0, observable)
    return out or [observable]


def parse_review(text: str) -> tuple[bool, str | None]:
    """Parse balasan judge-reviewer fresh-context (paket hardening bag. 2 +
    usulan Mirza 2026-07-19). Judge ADVISORY — vonis tetap mekanis — maka
    balasan tak ter-parse = fail-open (OK)."""
    outside = _FENCE_RE.sub("", text)
    m = re.search(r"^\s*REVIEW:\s*(OK|ISSUES)\s*$", outside,
                  re.MULTILINE | re.IGNORECASE)
    if m is None:
        return True, None
    if m.group(1).upper() == "OK":
        return True, None
    issues = outside[m.end():].strip()
    return False, issues or "(no detail given)"


def review_feedback(issues: str) -> str:
    """Bungkus temuan reviewer jadi feedback ke model utama. English."""
    return ("An independent review of your script found these issues:\n"
            f"{issues}\n"
            "Revise your script accordingly — or, where a point does not "
            "apply, keep your approach — then re-run the script to see "
            "REPRO_STATUS: FAIL and declare DONE again.")


def literal_emitted_by_script(script: str, literal: str) -> bool:
    """Marker milik skenario sah hanya bila script MENCETAKNYA (baris
    emisi print/write), bukan sekadar MENCARINYA di output framework.
    Lahir dari r26: token hantu 'Restarting...' lolos grep karena literal
    itu ada di baris pencarian `if ... in line` script sendiri."""
    for line in script.splitlines():
        if literal in line:
            head = line.split(literal, 1)[0]
            if ("print(" in head or "stdout.write" in head
                    or "stderr.write" in head):
                return True
    return False


def observable_rejection(observable: str | None) -> str:
    """Pesan penolakan DONE untuk klaim observable. English (model-facing)."""
    if observable is None:
        return ("Not done yet: state your PASS observable on its own line in "
                "this exact form: PASS_OBSERVABLE: <the exact literal string "
                "your script matches on to decide PASS>. Then declare DONE "
                "again.")
    return (f"Not done yet: the exact string '{observable}' does not appear "
            "in the repository source, and your own script does not print "
            "it either — so nothing can ever produce it. Either quote a "
            "message exactly as it is written in the repository source "
            "(open the file with a bash action first), or have your script "
            "print this marker itself. Then re-run the script to see "
            "REPRO_STATUS: FAIL and declare DONE with the corrected "
            "PASS_OBSERVABLE line.")


_REPRO_RUN_RE = re.compile(r"python[\d.]*\s+\S*repro\.py")


def is_repro_run(cmd: str) -> bool:
    """Apakah command bash ini benar-benar MENJALANKAN repro.py.

    Deteksi lama ("repro.py" in cmd) menghitung aksi tulis-file heredoc
    sebagai run gagal → retry phantom di events.jsonl (temuan analisa
    r20–r22 bersama Mirza)."""
    return _REPRO_RUN_RE.search(cmd) is not None


def mixed_block_note(cmd: str) -> str | None:
    """Blok bash yang MENJALANKAN repro.py tapi juga memuat perintah lain
    (kelas r35: `sed ... && python repro.py`) — driver hanya mengeksekusi
    repro run (di sandbox segar); perintah lain diam-diam tak pernah jalan
    dan model tersesat mengira efeknya terjadi. Beri tahu eksplisit."""
    extras = [
        ln for ln in (l.strip() for l in cmd.splitlines())
        if ln and not ln.startswith("#") and _REPRO_RUN_RE.search(ln) is None
    ]
    if not extras:
        return None
    return ("Note: only `python /testbed/.pipe/repro.py` was executed — "
            "always in a fresh sandbox — and the other commands in that "
            "block were not run. Put non-repro commands in their own "
            "```bash block; changes to the repository cannot affect the "
            "fresh-sandbox verdict anyway.")


def repeated_error_note(prev_why: str | None, why: str) -> str | None:
    """Injeksi eskalatif saat retry membawa alasan IDENTIK dengan retry
    sebelumnya (r21: TypeError yang sama 6× berturut-turut — feedback
    traceback mentah saja tidak mengubah perilaku model)."""
    if prev_why is None or prev_why != why:
        return None
    detail = why.split("last output line:", 1)
    tail = detail[1].strip() if len(detail) == 2 else why
    return (f"The same error occurred again: {tail}\n"
            "Your previous edit did not change the failing code path. The "
            "traceback names the exact file and line — open your script, "
            "find that line, and change that specific line before running "
            "again.")


def retry_reason(output: str, exit_code: int, max_len: int = 200) -> str:
    """Ringkasan satu baris (English) untuk detail.why event retry —
    permintaan Mirza 2026-07-18: tiap retry membawa alasan aktualnya,
    bukan label generik yang sama."""
    last = ""
    for line in reversed(output.splitlines()):
        if line.strip():
            last = line.strip()
            break
    why = f"repro run exited {exit_code} without REPRO_STATUS: FAIL"
    if last:
        why += f"; last output line: {last}"
    else:
        why += "; the run produced no output"
    return why if len(why) <= max_len else why[:max_len - 1] + "…"


def _tail(s: str, n: int) -> str:
    return s if len(s) <= n else s[-n:]


def exact_status(out: str) -> str | None:
    """Status token BARIS-EKSAK (kontrak: "the LAST line ... exactly").

    Standar TUNGGAL untuk "FAIL tersaksikan" — audit 2026-07-19: cek
    substring mid-loop vs regex pair menghasilkan dua vonis berbeda atas
    output yang sama (`REPRO_STATUS: FAIL (Got foo...)`) dan model
    "berdebat" dengan harness 3 turn."""
    m = re.findall(r"^REPRO_STATUS: (PASS|FAIL)\s*$", out, re.MULTILINE)
    return m[-1] if m else None


def token_format_note(out: str) -> str | None:
    """Sinyal: teks REPRO_STATUS ada tapi tak pernah sebagai baris eksak
    → beri tahu model persis apa yang salah (bukan menebak 3 turn)."""
    if "REPRO_STATUS" not in out or exact_status(out) is not None:
        return None
    return ("Your output mentions REPRO_STATUS but never as an exact "
            "line. The line must be exactly `REPRO_STATUS: FAIL` or "
            "`REPRO_STATUS: PASS` — nothing before or after it on that "
            "line. Print the verdict token alone and put any explanation "
            "on its own separate line.")


def fresh_pair_meta(out1: str, out2: str, exit1: int | None,
                    exit2: int | None, tail_chars: int = 200) -> dict:
    """Detail terstruktur pre-check pair utk events.jsonl — audit
    2026-07-19: event pair-reject string konstan membuat penyebab
    (format token vs crash) tak terbedakan tanpa membuka console."""
    return {"status1": exact_status(out1), "status2": exact_status(out2),
            "exit1": exit1, "exit2": exit2,
            "run1_tail": _tail(out1.strip(), tail_chars),
            "run2_tail": _tail(out2.strip(), tail_chars)}


def fresh_pair_rejection(out1: str, out2: str,
                         tail_chars: int = 800) -> str | None:
    """Vonis pre-check DUA run sandbox segar saat DONE — mirror gate
    (reproduce_gates.evaluate_gates): kedua run wajib mencetak
    REPRO_STATUS: FAIL. Lahir dari r16 (state-dependence, run tunggal
    cukup) lalu r20 (script flaky: run-1 FAIL sah, run-2 diagnostik
    control tanpa token — pre-check 1x lolos, gate 2x menangkap).
    Kegagalan diumpankan balik + injeksi aturan kontrak terkait
    (rule_catalog)."""
    from harness.stages import rule_catalog

    s1, s2 = exact_status(out1), exact_status(out2)
    if s1 == "FAIL" and s2 == "FAIL":
        return None

    parts = ["Not done yet: I ran your script twice, each time in a fresh "
             "sandbox (a clean copy of the repository, nothing else), and "
             "the runs did not both print REPRO_STATUS: FAIL.",
             f"Run 1 output tail:\n{_tail(out1, tail_chars)}",
             f"Run 2 output tail:\n{_tail(out2, tail_chars)}"]
    if s1 is None or s2 is None:
        parts.append(rule_catalog.inject("self-contained"))
    else:
        parts.append(rule_catalog.inject("repeatable"))
    if "control" in (out1 + out2).lower():
        parts.append(rule_catalog.inject("positive-control"))
    parts.append("Fix the script, re-run it to see REPRO_STATUS: FAIL, "
                 "then declare DONE.")
    return "\n\n".join(parts)


def next_step_nudge(observed_fail: bool, has_repro_md: bool) -> str | None:
    """Pemutus loop degeneratif (r13): model sudah menyaksikan FAIL tapi
    terus menulis-ulang script tiap turn tanpa pernah menyetor repro.md.
    Feedback identik tiap turn = attractor repetisi bagi model kecil;
    nudge ini mengubah feedback dan menunjuk langkah berikutnya."""
    if observed_fail and not has_repro_md:
        return ("You have already run your script and REPRO_STATUS: FAIL was "
                "observed — that evidence is sufficient. Submit the "
                "```repro.md block now (the exact lines listed in the "
                "contract), then declare DONE.")
    return None


def has_fences(text: str) -> bool:
    """Ada minimal satu fenced block (apa pun info-string-nya)."""
    return _FENCE_RE.search(text) is not None


def format_reminder() -> str:
    """Pengingat bentuk aksi yang sah — dikirim saat reply berisi fence tapi
    NOL aksi ter-parse. Lahir dari r11 (11422): Gemma memakai
    `<|tool_call>` + fence ```python selama ~11 turn; file tak pernah
    tertulis dan feedback generik tidak menyebut bentuk yang benar."""
    return ("None of your fenced blocks were executed. Only these forms are "
            "executed, chosen by the text right after the opening backticks:\n"
            "```bash            -> run a shell command\n"
            "```file:/abs/path  -> write that file with the block's content\n"
            "```repro.md        -> submit the repro.md artifact\n"
            "A ```python block is NOT executed — to create a script, put its "
            "content in a ```file:/testbed/.pipe/repro.py block, then run it "
            "with a ```bash block.")


def done_rejection_localize(has_localize_md: bool, ran_any_bash: bool) -> str | None:
    """Aturan SELESAI stage LOCALIZE. None = diterima.

    Evidensi minimal: model harus benar-benar melakukan eksplorasi (>=1 aksi
    bash) sebelum menyerahkan peta — melarang localize buta dari prior.
    """
    if not has_localize_md:
        return ("Not done yet: submit the ```localize.md block first, then "
                "declare DONE.")
    if not ran_any_bash:
        return ("Not done yet: do some exploration first — open the relevant "
                "code with bash actions, then submit your map.")
    return None
