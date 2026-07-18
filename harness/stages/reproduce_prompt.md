# REPRODUCE stage — contract for the model (frontier and Gemma alike)

You are the REPRODUCE stage. The sandbox `/testbed` contains the repository at
the BASE COMMIT (the bug is present). You receive a PROBLEM STATEMENT (the
issue). Your ONLY job is to reproduce the bug — you are FORBIDDEN from fixing
any code.

## Required output

1. **Repro script** at `/testbed/.pipe/repro.py`:
   - Self-contained: it must run with `python /testbed/.pipe/repro.py` in a
     fresh sandbox with no other manual steps (set up any settings/app it
     needs by itself; never depend on modules or files you did not create
     inside the script).
   - Idempotent: running it repeatedly yields identical results (clean up any
     state you create; never leave files/migrations that change the next run).
   - The LAST line of its output MUST be exactly one of:
     - `REPRO_STATUS: FAIL` → the bug is VISIBLE (expected at base commit)
     - `REPRO_STATUS: PASS` → the behavior is correct (later, once fixed)
   - Its predicate must test the OBSERVABLE THE USER COMPLAINS ABOUT in the
     issue (output, value, exit code, the exception they mention) — NOT your
     interpretation of the internal cause. Ask yourself: "if a maintainer
     fixed this bug in any legitimate way, would my script flip FAIL → PASS?"
     If you are not certain the answer is YES, your predicate is wrong.
   - Imitate the user's action path from the issue (same entry point, same
     command shape). Do not mock or probe the internals of the very component
     under test — a mocked internal can make your predicate impossible to
     flip even by a correct fix.

2. **`repro.md`** — you write ONLY the interpretive part (fixed format):

```
SYMPTOM: <one sentence: the symptom as the user experiences it>
TRIGGER: <the condition/steps that trigger it>
EXPECTED vs ACTUAL:
EXPECTED: <the correct behavior>
ACTUAL: <the wrong behavior observed now>
```

The harness appends the mechanical slots itself: `REPRO COMMAND` (always
`python /testbed/.pipe/repro.py`) and `CONFIRMED-AT-BASE` (yes only if the
harness has witnessed your script print `REPRO_STATUS: FAIL`). You cannot set
these yourself — run your script for real and let the evidence speak.

## What the harness does after you (mechanical gates — know them to pass)

1. Anti-vacuous: your script is run in a FRESH sandbox; it must print
   `REPRO_STATUS: FAIL` (bug visible at base). `PASS` at base = REJECTED.
2. Self-contained: run in a NEW container (not yours) — scaffolding errors
   (ModuleNotFoundError, settings) = REJECTED.
3. Idempotent: run twice in a row; the `REPRO_STATUS` line and the core
   symptom must be identical.
4. Format: the final `repro.md` (your part + the harness-appended slots) must
   have all 5 slots; the `REPRO_STATUS:` line must be exact.

You may experiment as much as you need BEFORE writing the final output (try a
script, revise the predicate, repeat). Only the final output is judged.
