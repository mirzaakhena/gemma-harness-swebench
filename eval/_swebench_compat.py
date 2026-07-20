"""Kompat Windows utk paket swebench: modul `resource` (Unix-only) di-shim
sebelum import swebench apa pun. SEMUA import swebench di repo ini lewat
ensure_resource_shim() dulu — import langsung crash di Windows."""
from __future__ import annotations

import sys
import types


def ensure_resource_shim() -> None:
    # Shim ini HANYA relevan di Windows (modul stdlib `resource` tak ada di
    # sana). Di Linux/macOS (mis. CI masa depan) `resource` sudah ada di
    # stdlib — jangan pernah clobber modul asli itu dgn shim palsu.
    if sys.platform != "win32":
        return
    if "resource" in sys.modules:
        return
    m = types.ModuleType("resource")
    m.getrlimit = lambda *a: (0, 0)
    m.setrlimit = lambda *a: None
    m.RLIMIT_NOFILE = 7
    sys.modules["resource"] = m
