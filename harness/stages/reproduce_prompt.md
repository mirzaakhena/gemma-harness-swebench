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
     Ask yourself: "if a maintainer fixed this bug in any legitimate way,
     would my script flip FAIL → PASS?" Make the answer YES.
   - If your scenario crashes for a reason that is not the reported symptom,
     repair the script — a crash counts as FAIL only when the crash IS the
     symptom the user reports.

2. **`repro.md`** containing exactly these lines:

```
SYMPTOM: <one sentence: the symptom as the user experiences it>
TRIGGER: <the condition/steps that trigger it>
EXPECTED vs ACTUAL:
EXPECTED: <the correct behavior>
ACTUAL: <the wrong behavior observed now>
```

## Definition of done

- You have run your script at the base commit and seen `REPRO_STATUS: FAIL`
  in its output with your own eyes.
- The script sets up everything it needs and leaves nothing behind.
- You have submitted `repro.md`.

Work iteratively: try, observe the output, revise. Only your final outputs
count.
