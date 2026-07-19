"""Tracer in-container Lever L#3: jalankan repro.py di bawah sys.settrace,
kumpulkan file REPO (/testbed, exclude workspace .pipe) yang TEREKSEKUSI.

Script ini di-mount & dieksekusi DI DALAM container segar oleh
localize_trace.run_trace() — stdlib murni, tanpa import harness, agar jalan
di python image case apa pun:

    python /tracer-in/localize_tracer.py /testbed/.pipe/repro.py

Pool ditulis ke /tmp/trace_pool.json (list path relatif thd /testbed/);
runner membacanya lewat sentinel di stdout. Hanya call-events (tanpa line
tracing) — murah; import modul pun tercatat karena eksekusi body modul
adalah call frame.

Batas diketahui (dicatat sadar): child process TIDAK ter-trace — repro
kedua case target (11964, 11797) in-process penuh, terverifikasi empiris
pool memuat file gold masing-masing (enums.py, lookups.py).
"""
import json
import runpy
import sys
import threading

REPO_PREFIX = "/testbed/"
EXCLUDE_PREFIX = "/testbed/.pipe/"
OUT_PATH = "/tmp/trace_pool.json"

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


def main():
    script = sys.argv[1]
    sys.argv = [script]
    threading.settrace(_tracer)
    sys.settrace(_tracer)
    exit_code = 0
    try:
        runpy.run_path(script, run_name="__main__")
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 0
    except BaseException as e:
        sys.stderr.write("TRACER_NOTE: repro raised %r\n" % (e,))
        exit_code = 1
    finally:
        sys.settrace(None)
        threading.settrace(None)
    with open(OUT_PATH, "w") as f:
        json.dump(sorted(_files), f)
    sys.stderr.write("TRACER_EXIT: %d\n" % exit_code)


if __name__ == "__main__":
    main()
