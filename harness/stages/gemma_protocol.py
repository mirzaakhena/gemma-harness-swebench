"""Parser protokol teks untuk driver Gemma.

Aksi = fenced block dengan info-string khusus:
  ```bash            -> jalankan command di sandbox
  ```file:<path>     -> tulis file di sandbox
  ```repro.md        -> artefak final repro.md
Fenced block dengan bahasa lain (python, dsb.) BUKAN aksi.
Penanda selesai: baris `SELESAI` di LUAR fenced block.
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
        elif info == "repro.md":
            actions.append(Action(kind="repro.md", arg=None, body=body))
    return actions


def has_done(text: str) -> bool:
    outside = _FENCE_RE.sub("", text)
    return any(line.strip() == "SELESAI" for line in outside.splitlines())


def done_rejection_reason(has_repro_md: bool, observed_fail: bool) -> str | None:
    """Aturan bukti-dulu-baru-SELESAI. None = SELESAI diterima.

    Lahir dari kegagalan run r2 (11422): model menyerahkan CONFIRMED-AT-BASE
    yes + SELESAI padahal eksekusi repro-nya crash — konfirmasi tanpa bukti.
    """
    if not has_repro_md:
        return ("Belum bisa SELESAI: blok ```repro.md belum kamu serahkan.")
    if not observed_fail:
        return ("Belum bisa SELESAI: aku belum pernah melihat eksekusi "
                "`python /testbed/.pipe/repro.py` yang mencetak "
                "`REPRO_STATUS: FAIL` di sesi ini. Jalankan repro-mu, lihat "
                "outputnya, perbaiki sampai FAIL terlihat — baru SELESAI.")
    return None
