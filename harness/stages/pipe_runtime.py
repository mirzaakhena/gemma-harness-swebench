"""pipe_runtime — application runtime helper shipped into the sandbox.

The harness copies this file to /testbed/.pipe/pipe_runtime.py in the work
container AND in every fresh gate container, so a repro script can rely on
`from pipe_runtime import App` while staying fully self-contained.

Division of labor (project principle): the model decides WHAT to run (the
command, the ready line, the predicate); this module owns the mechanics that
repeatedly broke hand-rolled scripts:

- readiness: `start()` blocks until the app prints its ready line, then
  settles one extra beat so periodic watchers capture their baseline;
- re-readiness: `wait_ready()` does the same for every reload/restart;
- visibility: every child line is echoed to this process's stdout, so
  bootstrap errors are never silently swallowed.

Target runtime: Python 3.6 inside the testbed containers — only syntax and
stdlib calls that exist there are allowed (guard: test_pipe_runtime).
Runs on POSIX; degrades gracefully on Windows (used there only by tests).
"""
import os
import signal
import subprocess
import sys
import threading
import time


class App(object):
    """A child application with mechanical readiness handling.

    Usage:
        app = App(["python", "manage.py", "runserver"],
                  ready_token="Watching for file changes with StatReloader",
                  cwd=project_dir)
        app.start()               # ready + settled baseline
        ...trigger a reload...
        app.wait_ready()          # True when the app came back up (settled)
        app.wait_for("some line") # any other observable line
        app.stop()
    """

    def __init__(self, cmd, ready_token, cwd=None, interval=1.0, settle=None):
        if not ready_token:
            raise ValueError("ready_token is required")
        self.cmd = list(cmd)
        self.ready_token = ready_token
        self.cwd = cwd
        self.interval = float(interval)
        # settle: how long to wait after each ready line so a periodic
        # watcher records its baseline snapshot before any trigger fires.
        self.settle = float(settle) if settle is not None else max(
            2.0, 2.0 * self.interval)
        self._proc = None
        self._lines = []          # every echoed line, in order
        self._ready_count = 0     # occurrences of ready_token seen
        self._ready_consumed = 0  # occurrences already waited-for
        self._cond = threading.Condition()
        self._reader = None

    # -- internals ----------------------------------------------------------

    def _pump(self):
        try:
            for line in self._proc.stdout:
                sys.stdout.write("[app] " + line)
                sys.stdout.flush()
                with self._cond:
                    self._lines.append(line)
                    if self.ready_token in line:
                        self._ready_count += 1
                    self._cond.notify_all()
        except Exception:
            pass
        with self._cond:
            self._cond.notify_all()  # bangunkan penunggu saat stream tutup

    def _dead(self):
        return self._proc is None or self._proc.poll() is not None

    def _wait(self, predicate, timeout):
        deadline = time.time() + timeout
        with self._cond:
            while True:
                if predicate():
                    return True
                if self._dead() and not predicate():
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        return False
                    # stream mungkin masih flush; tunggu sebentar lalu final
                    self._cond.wait(min(0.2, remaining))
                    if predicate():
                        return True
                    if self._dead():
                        return False
                    continue
                remaining = deadline - time.time()
                if remaining <= 0:
                    return False
                self._cond.wait(min(0.2, remaining))

    # -- API ----------------------------------------------------------------

    def start(self, timeout=30):
        """Spawn the app, wait for the ready line, settle the baseline.

        Raises RuntimeError (with the echoed output already on stdout) when
        the app exits or the ready line does not appear within timeout.
        """
        kwargs = {}
        if os.name == "posix":
            kwargs["preexec_fn"] = os.setsid  # process group utk stop()
        self._proc = subprocess.Popen(
            self.cmd, cwd=self.cwd, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1,
            **kwargs)
        self._reader = threading.Thread(target=self._pump)
        self._reader.daemon = True
        self._reader.start()
        ok = self._wait(lambda: self._ready_count >= 1, timeout)
        if not ok:
            why = ("application exited before printing the ready line"
                   if self._dead() else
                   "ready line not seen within {}s".format(timeout))
            self.stop()
            raise RuntimeError(
                "pipe_runtime: app failed to become ready ({}); its output "
                "is echoed above with the [app] prefix".format(why))
        self._ready_consumed = 1
        time.sleep(self.settle)
        return self

    def wait_ready(self, timeout=15):
        """Wait for the NEXT ready line (an app reload/restart), then settle.

        Returns True when seen (baseline settled again), False on timeout —
        absence of a reload may be the very symptom under test, so this
        never raises.
        """
        target = self._ready_consumed + 1
        ok = self._wait(lambda: self._ready_count >= target, timeout)
        if not ok:
            return False
        with self._cond:
            self._ready_consumed = self._ready_count
        time.sleep(self.settle)
        return True

    def wait_for(self, token, timeout=15):
        """Wait until any echoed line contains token (past lines count)."""
        return self._wait(
            lambda: any(token in ln for ln in self._lines), timeout)

    def poll(self):
        """Child exit code, or None while it is still running."""
        return None if self._proc is None else self._proc.poll()

    def stop(self):
        """Terminate the app (and its process group on POSIX)."""
        if self._proc is None or self._proc.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            else:
                self._proc.terminate()
        except (ProcessLookupError, OSError):
            pass
        try:
            self._proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                if os.name == "posix":
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
                else:
                    self._proc.kill()
            except (ProcessLookupError, OSError):
                pass
            self._proc.wait()
