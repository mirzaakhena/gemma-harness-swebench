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
        return ("Cannot accept DONE: you have not submitted the ```repro.md "
                "block yet.")
    if not observed_fail:
        return ("Cannot accept DONE: I have not witnessed any execution of "
                "`python /testbed/.pipe/repro.py` printing "
                "`REPRO_STATUS: FAIL` in this session. Run your repro, "
                "observe its output, and fix it until FAIL is visible — "
                "only then declare DONE.")
    return None


def done_rejection_localize(has_localize_md: bool, ran_any_bash: bool) -> str | None:
    """Aturan SELESAI stage LOCALIZE. None = diterima.

    Evidensi minimal: model harus benar-benar melakukan eksplorasi (>=1 aksi
    bash) sebelum menyerahkan peta — melarang localize buta dari prior.
    """
    if not has_localize_md:
        return ("Cannot accept DONE: you have not submitted the "
                "```localize.md block yet.")
    if not ran_any_bash:
        return ("Cannot accept DONE: you have performed zero exploration "
                "(no bash actions). Read the code in the sandbox first; "
                "localizing without opening a single file is guessing.")
    return None
