"""Test Lever L#4 (helper probe): probe_runtime di-ship ke workspace probe +
kontrak menegaskan keberadaannya.

Latar (autopsi 11964, vault R-dev Log): kelas kegagalan "probe-crash ->
fallback-statis" — probe ber-Model crash di boilerplate app-registry, model
lalu memilih kandidat dari plausibility statis dan DONE tetap diterima.
Fungsi setup()/create_tables() sendiri butuh Django + container — diuji
smoke test di image case (bukan pytest host); di sini yang dijaga: bentuk
modul, bahasa, wiring shipping, dan drift kontrak.
"""
from pathlib import Path

STAGES = Path(__file__).resolve().parent.parent / "harness" / "stages"


def test_probe_runtime_importable_and_has_api():
    from harness.stages import probe_runtime
    assert callable(probe_runtime.setup)
    assert callable(probe_runtime.create_tables)


def test_probe_runtime_import_has_no_django_side_effect():
    # Import di host (tanpa Django) harus aman: django hanya di-import
    # lazily di dalam setup()/create_tables().
    import importlib

    import harness.stages.probe_runtime as pr
    importlib.reload(pr)  # akan meledak bila import-time butuh django


def test_probe_runtime_model_facing_text_is_english():
    # Model bisa membaca file ini via cat — docstring pemakaian English.
    text = (STAGES / "probe_runtime.py").read_text(encoding="utf-8")
    usage = text.split("Catatan harness")[0]
    for word in ("Belum", "kamu", "dulu", "berkas", "jalankan"):
        assert word not in usage, f"teks model-facing ber-Indonesia: {word}"
    assert "probe_runtime.setup()" in usage
    assert "create_tables" in usage


def test_driver_ships_probe_runtime_to_workspace():
    # Drift-guard wiring: driver menulis modul ke /testbed/.pipe/ container
    # kerja (tempat probe dieksekusi).
    src = (STAGES / "run_localize_gemma.py").read_text(encoding="utf-8")
    assert '/testbed/.pipe/probe_runtime.py' in src


def test_contract_names_probe_runtime():
    text = (STAGES / "localize_prompt.md").read_text(encoding="utf-8")
    assert "probe_runtime.setup()" in text
    assert "create_tables" in text
    assert "app_label" in text
