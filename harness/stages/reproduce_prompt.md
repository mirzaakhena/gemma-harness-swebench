# REPRODUCE stage — task contract

You are the REPRODUCE stage. The sandbox `/testbed` contains the repository at
the BASE COMMIT, where the reported bug is present. You receive a PROBLEM
STATEMENT (the user's issue). Your scope: demonstrate the bug with a runnable
script. The fix belongs to a later stage.

## Your outputs

1. **Repro script at `/testbed/.pipe/repro.py`** with these properties:
   - It runs with `python /testbed/.pipe/repro.py` and nothing else: create
     any settings, app, or fixtures it needs inside the script itself.
   - It is repeatable: running it twice produces identical output; clean up
     any state it creates.
   - The LAST line of its output is exactly one of:
     - `REPRO_STATUS: FAIL` — the bug is visible (what you must observe at
       the base commit)
     - `REPRO_STATUS: PASS` — the behavior is correct (what a fixed codebase
       will print)
   - Its predicate tests the observable the user complains about in the issue
     (output, value, exit code, the exception they name). Follow the user's
     action path: the same entry point and command shape the issue describes.
     When the behavior depends on how the program is launched (the entry
     point, the command line, a running server), your script spawns that
     launch as a real child process and observes it end to end — launch
     state (the entry-point module, argv, environment) exists only inside a
     process actually started that way; a launch imitated inside your own
     repro process observes a different scenario. Ask yourself: "if a
     maintainer fixed this bug in any legitimate way, would my script flip
     FAIL → PASS?" Make the answer YES.
   - Prefer an observable your own scenario emits: when you control the
     child entry-point script, have it print a short marker line that
     directly reports the behavior under test, then assert on that exact
     marker. A framework log message is a valid observable only when you
     have quoted it exactly from the repository source.
   - Give sampling mechanisms their baseline: when your trigger must be
     noticed by a mechanism that checks state periodically (a watcher, a
     poller), fire the trigger only after that mechanism has observably
     finished starting up PLUS one full sampling interval — read the
     interval from the repository source. After the trigger, wait for the
     resulting observable with a bounded deadline of several intervals.
   - FAITHFUL SETUP: obtain the thing under test the way real operation
     produces it — reach the state you assert against by exercising the real
     code path or entry point, so its genuine attributes hold exactly as they
     really are. Building the object yourself and assigning it the attributes
     you assume makes your script observe a situation that may never occur —
     then PASS/FAIL measures the wrong scenario. Set values yourself only for
     genuinely external inputs the real path itself would receive.
   - PASS-condition fidelity: the ONLY way your script prints
     `REPRO_STATUS: PASS` is that the specific reported defect is actually
     fixed — no OR of conditions where one side is always true, no unrelated
     already-working path. At base it prints FAIL for the RIGHT reason:
     because the specific defective behavior is present.
   - Source the PASS side: you cannot observe the correct behavior at the
     base commit (the bug prevents it), so derive the exact expected
     observable — the precise log message, attribute, or value — by READING
     the repository source that produces it, and quote it exactly. A
     plausible-sounding message from your memory of similar tools will not
     match reality.
   - If your scenario crashes for a reason that is not the reported symptom,
     repair the script — a crash counts as FAIL only when the crash IS the
     symptom the user reports.

2. **`repro.md`** containing exactly these lines:

```
SYMPTOM: <one sentence: the symptom as the user experiences it>
TRIGGER: <the exact runtime state/input that fires it, stated as observed values you actually probed — not a hypothesis>
EXPECTED vs ACTUAL:
EXPECTED: <the correct behavior your script asserts>
ACTUAL: <the wrong behavior observed now>
```

Submit an early draft of `repro.md` as soon as your first probe succeeds, and
refine it as you learn — an early rough draft beats a polished one that never
gets submitted.

## Definition of done

- You have run your script at the base commit and seen `REPRO_STATUS: FAIL`
  in its output with your own eyes.
- The script sets up everything it needs and leaves nothing behind.
- You have submitted `repro.md`.

Work iteratively: try, observe the output, revise. Only your final outputs
count.
