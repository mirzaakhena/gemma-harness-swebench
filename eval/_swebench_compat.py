"""Kompat Windows utk paket swebench: modul `resource` (Unix-only) di-shim
sebelum import swebench apa pun. SEMUA import swebench di repo ini lewat
ensure_resource_shim() dulu — import langsung crash di Windows."""
from __future__ import annotations

import sys
import types


def ensure_resource_shim() -> None:
    if "resource" in sys.modules:
        return
    m = types.ModuleType("resource")
    m.getrlimit = lambda *a: (0, 0)
    m.setrlimit = lambda *a: None
    m.RLIMIT_NOFILE = 7
    sys.modules["resource"] = m
