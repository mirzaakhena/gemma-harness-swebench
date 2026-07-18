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
            # 'changed, reloading.') — kutip berpasangan bukan bagian
            # observable, buang satu lapis.
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
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


def observable_rejection(observable: str | None) -> str:
    """Pesan penolakan DONE untuk klaim observable. English (model-facing)."""
    if observable is None:
        return ("Not done yet: state your PASS observable on its own line in "
                "this exact form: PASS_OBSERVABLE: <the exact literal string "
                "your script matches on to decide PASS>. Then declare DONE "
                "again.")
    return (f"Not done yet: the exact string '{observable}' appears nowhere "
            "in the repository source or in your script. Open the module "
            "that produces your PASS observable, quote the message exactly "
            "as written there, update your script to match it, re-run the "
            "script to see REPRO_STATUS: FAIL, then declare DONE with the "
            "corrected PASS_OBSERVABLE line.")


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
