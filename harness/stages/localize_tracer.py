"""Tracer in-container Lever L#3: kumpulkan file REPO (/testbed, exclude
workspace .pipe) yang TEREKSEKUSI selama repro berjalan.

Mode pemakaian (sejak abort 11910 l-dev r1 — repro yang menjalankan Django
via child process menghasilkan pool kosong pada tracer parent-only):
modul ini diaktifkan lewat sitecustomize (trace_sitecustomize.py di-copy
runner ke /tmp/tracehook/sitecustomize.py + PYTHONPATH) sehingga SETIAP
proses Python — induk maupun child spawn-an repro — memasang tracer dan
menyetor daftar filenya sendiri ke $TRACE_POOL_DIR/pool-<pid>-<rand>.json
saat exit; runner meng-union semua setoran. Stdlib murni, py3.6+.

Batas diketahui (dicatat sadar): proses yang mati tak wajar (SIGKILL,
os._exit) tidak sempat menyetor — setoran proses lain tetap masuk.
"""
import atexit
import binascii
import json
import os
import sys
import threading

REPO_PREFIX = "/testbed/"
EXCLUDE_PREFIX = "/testbed/.pipe/"

_files = set()


def keep(filename):
    """File layak masuk pool: source .py di bawah repo, di luar .pipe."""
    return (filename.startswith(REPO_PREFIX)
            and not filename.startswith(EXCLUDE_PREFIX)
            and filename.endswith(".py"))


def relativize(filename):
    return filename[len(REPO_PREFIX):]


def _tracer(frame, event, arg):
    if event == "call":
        fn = frame.f_code.co_filename
        if keep(fn):
            _files.add(relativize(fn))
    return None  # tanpa local trace -> call-events saja


def _dump(out_dir):
    sys.settrace(None)
    name = "pool-%d-%s.json" % (
        os.getpid(), binascii.hexlify(os.urandom(4)).decode("ascii"))
    try:
        with open(os.path.join(out_dir, name), "w") as f:
            json.dump(sorted(_files), f)
    except OSError:
        pass  # setoran gagal tak boleh mengubah exit status proses target


def install():
    """Pasang tracer bila env TRACE_POOL_DIR di-set (dipanggil
    sitecustomize di tiap proses trace run); di luar itu no-op."""
    out_dir = os.environ.get("TRACE_POOL_DIR")
    if not out_dir:
        return
    threading.settrace(_tracer)
    sys.settrace(_tracer)
    atexit.register(_dump, out_dir)
