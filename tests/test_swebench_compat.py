"""Test shim resource utk paket swebench di Windows."""
import sys


def test_shim_allows_swebench_import():
    from eval._swebench_compat import ensure_resource_shim
    ensure_resource_shim()
    from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS
    assert "django/django" in MAP_REPO_VERSION_TO_SPECS


def test_shim_idempotent():
    from eval._swebench_compat import ensure_resource_shim
    ensure_resource_shim()
    before = sys.modules["resource"]
    ensure_resource_shim()
    assert sys.modules["resource"] is before


def test_shim_skips_on_non_win32(monkeypatch):
    """Di platform non-Windows, shim tidak dipasang (guard early-return)."""
    from eval._swebench_compat import ensure_resource_shim
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delitem(sys.modules, "resource", raising=False)
    ensure_resource_shim()
    assert "resource" not in sys.modules
