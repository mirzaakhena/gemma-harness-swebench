# LOCALIZE stage — task contract

You are the LOCALIZE stage. The sandbox `/testbed` contains the repository at
the BASE COMMIT, where the reported bug is present. You receive the PROBLEM
STATEMENT (the user's issue) plus the REPRODUCE stage artifacts: `repro.md`
and a verified repro script at `/testbed/.pipe/repro.py` (run it any time:
`python /testbed/.pipe/repro.py` prints `REPRO_STATUS: FAIL` while the bug
exists).

Your scope: point at the ROOT-CAUSE LOCATION — the place where the fix
belongs. The fix itself belongs to a later stage. The repository is your
reading material; your writable workspace is `/testbed/.pipe/` (probe
scripts, notes).

## Your output: `localize.md`

```
chosen: <number of the chosen candidate; 1 if you only had one>
file: <path relative to the repo root, e.g. django/utils/autoreload.py>
lines: <N-M — a range of at most 200 lines containing the mechanism site>
what: <what kind of change is needed at this location (description, not a patch)>
why: <the mechanism that makes this location the ROOT of the symptom, not merely a place the symptom passes through>
evidence: <concrete proof in the form "function X around line Y does Z, which causes the symptom; proven by ...">
```

`file` must be a real file in the repository; `lines` must lie within it.

## Quality rules

1. **Attribute the site, not the propagation.** Evidence points at code that
   PERFORMS the causal mechanism ("function X at line Y does Z") — not a
   description that the symptom "changes/propagates through" some file. If
   all you can describe is the flow of the symptom, keep digging.
2. **Attribute to the layer that OWNS the wrong decision** — the specific
   class, lookup, or method where the incorrect value is first computed —
   not the generic infrastructure (a base class, a query builder, a
   compiler) that renders, transports, or executes it downstream. Landing
   on a broad shared module is a signal to look one level upstream: find
   which narrower definition site feeds it the wrong decision.
3. **When static evidence runs out, get execution evidence.** Write and run
   small probe scripts in `/testbed/.pipe/` (prints, direct calls into
   suspect functions) to discriminate between candidates — never pick a
   candidate on plausibility alone. When more than one layer could host
   the fix, run a probe that discriminates between them; a file appearing
   in the traceback or execution path is not evidence that the fix
   belongs there.
4. **The narrower the range, the better.** Pointing at `1-1500` is pointing
   at nothing.
5. Before submitting, ask yourself: "if an engineer read only my
   localize.md, would they immediately know WHAT to edit and WHERE?"

Work iteratively: explore, probe, revise. Only your final output counts.
