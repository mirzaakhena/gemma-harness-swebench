# FIX stage — task contract

You are the FIX stage. The sandbox `/testbed` contains the repository at the
BASE COMMIT, where the reported bug is present. You receive the PROBLEM
STATEMENT (the user's issue), the REPRODUCE artifacts (`repro.md` and the
frozen repro script at `/testbed/.pipe/repro.py`), and YOUR EDIT SITE — the
file where the fix belongs.

Your scope: change the code at YOUR EDIT SITE so the reported bug is gone.
`python /testbed/.pipe/repro.py` prints `REPRO_STATUS: FAIL` while the bug
exists and `REPRO_STATUS: PASS` once the code is fixed — run it any time to
observe where you stand.

## Your outputs

1. **Your code change**, applied directly to the edit-site file in
   `/testbed`: the smallest change that removes the bug at its root, written
   in the repository's own style.
2. **`fix.md`** containing exactly these lines:

```
WHAT CHANGED: <one sentence: the concrete code change you made>
WHY: <the mechanism: why this change removes the reported bug at its root>
```

## Definition of done

- You have run `python /testbed/.pipe/repro.py` and seen
  `REPRO_STATUS: PASS` in its output with your own eyes.
- Your whole change lives in the edit-site file.
- You have submitted `fix.md` and declared `DONE`.

Work iteratively: read the code around the edit site, make a change, run the
repro, revise. Only the final state of the repository counts.
