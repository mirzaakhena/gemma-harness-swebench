"""sitecustomize untuk trace run L#3 — di-copy runner ke /tmp/tracehook/
sitecustomize.py dan diaktifkan via PYTHONPATH, sehingga SETIAP proses
Python (induk + child spawn-an repro) otomatis memasang tracer.

Lahir dari abort 11910 l-dev r1: repro menjalankan Django via child
process (`echo y | python manage.py makemigrations`) → tracer
parent-only menghasilkan pool kosong. Aktif hanya bila env
TRACE_POOL_DIR di-set (di luar trace run: no-op).
"""
try:
    import localize_tracer
    localize_tracer.install()
except Exception:
    pass  # trace hook tidak boleh mematikan proses target
