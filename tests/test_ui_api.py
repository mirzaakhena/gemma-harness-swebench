"""Test API JSON UI log viewer (ui/server.py) — serialisasi + HTTP layer."""
import json

from ui.server import run_index_verdict


# --- fixture artifacts sintetis ---------------------------------------------

def mk_run(root, campaign, case, rerun, verdict=None, pass_l1=None,
           started="2026-07-21T14:03:00+07:00"):
    """Satu run sintetis: dir + events.jsonl + runs.jsonl (+ verdict.json).

    verdict None -> run hidup tanpa verdict.json.
    """
    camp = root / campaign
    run_id = f"{campaign}--{case}--{rerun}"
    rd = camp / run_id
    rd.mkdir(parents=True)
    (rd / "events.jsonl").write_text(
        json.dumps({"ts": started, "event": "start"}) + "\n",
        encoding="utf-8")
    with (camp / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"run_id": run_id, "event": "start"}) + "\n")
        if verdict is not None:
            f.write(json.dumps({"run_id": run_id, "event": "end",
                                "verdict": verdict, "wall": 12.3}) + "\n")
    if verdict is not None:
        vj = {"phases": {"reproduce": {"verdict": verdict}},
              "started": started, "finished": started}
        if pass_l1 is not None:
            vj["pass_l1"] = pass_l1
        (rd / "verdict.json").write_text(json.dumps(vj), encoding="utf-8")
    return run_id


# --- run_index_verdict ------------------------------------------------------

def test_run_index_verdict_missing_verdict(tmp_path):
    assert run_index_verdict("r-dev", tmp_path) == ("-", "")


def test_run_index_verdict_broken_verdict(tmp_path):
    (tmp_path / "verdict.json").write_text("{rusak", encoding="utf-8")
    text, icon = run_index_verdict("r-dev", tmp_path)
    assert text == "(verdict.json rusak)" and icon == ""


def test_run_index_verdict_pass(tmp_path):
    rid = mk_run(tmp_path, "r-dev", "django__django-1", "r1",
                 verdict="pass", pass_l1=True)
    text, icon = run_index_verdict("r-dev", tmp_path / "r-dev" / rid)
    assert text == "pass" and icon.startswith("✅")


def test_run_index_verdict_merges_gold_wrong_file(tmp_path):
    rid = mk_run(tmp_path, "l-dev", "django__django-1", "r1", verdict="pass")
    run_dir = tmp_path / "l-dev" / rid
    (run_dir / "gold_eval.json").write_text(
        json.dumps({"qualified": False}), encoding="utf-8")
    text, icon = run_index_verdict("l-dev", run_dir)
    assert text == "wrong-file" and icon.startswith("❌")
